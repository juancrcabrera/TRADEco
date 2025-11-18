from datetime import datetime
from bson import ObjectId
import secrets
import string

class Transaction:
    """Modelo de Transacción para MongoDB"""
    
    # Estados posibles de una transacción
    STATUS = {
        'PENDING': 'pendiente',           # Reserva creada, esperando confirmación
        'CONFIRMED': 'confirmada',        # Vendedor confirmó la venta
        'PAYMENT_CONFIRMED': 'pago_confirmado',  # Comprador confirmó el pago
        'COMPLETED': 'completada',        # Transacción finalizada
        'CANCELLED': 'cancelada',         # Cancelada por alguna de las partes
        'DISPUTED': 'en_disputa'          # Hay un problema
    }
    
    def __init__(self, db):
        self.collection = db.transactions
        self._create_indexes()
    
    def _create_indexes(self):
        """Crear índices para búsquedas eficientes"""
        self.collection.create_index("transaction_code", unique=True)
        self.collection.create_index("product_id")
        self.collection.create_index("buyer_id")
        self.collection.create_index("seller_id")
        self.collection.create_index("status")
        self.collection.create_index("created_at")
    
    def _generate_transaction_code(self):
        """Generar código único de transacción"""
        # Formato: TRD-XXXXXX (6 caracteres alfanuméricos)
        chars = string.ascii_uppercase + string.digits
        code = ''.join(secrets.choice(chars) for _ in range(6))
        return f"TRD-{code}"

    def create(self, product_id, buyer_id, seller_id, product_data, buyer_data=None, seller_data=None):
        """
        Crear una nueva transacción (reserva)
        
        Args:
            product_id: ID del producto
            buyer_id: ID del comprador
            seller_id: ID del vendedor
            product_data: Datos del producto para el comprobante
        """
        # Generar código único
        transaction_code = self._generate_transaction_code()
        
        # Verificar que el código sea único (por si acaso)
        while self.collection.find_one({"transaction_code": transaction_code}):
            transaction_code = self._generate_transaction_code()
        
        transaction_data = {
            "transaction_code": transaction_code,
            "product_id": product_id,
            "buyer_id": buyer_id,
            "seller_id": seller_id,
            "buyer_username": buyer_data.get('username') if buyer_data else '',
            "seller_username": seller_data.get('username') if seller_data else '',
    
            # Datos del producto (snapshot para el comprobante)
            "product_snapshot": {
                "nombre": product_data.get("nombre"),
                "descripcion": product_data.get("descripcion"),
                "precio": product_data.get("precio"),
                "costo": product_data.get("costo", 0),
                "categoria": product_data.get("categoria"),
                "talla": product_data.get("talla"),
                "imagen_url": product_data.get("imagen_url")
            },
            
            # Estado de la transacción
            "status": self.STATUS['PENDING'],
            
            # Timeline de eventos
            "timeline": [
                {
                    "status": self.STATUS['PENDING'],
                    "timestamp": datetime.utcnow(),
                    "message": "Reserva creada"
                }
            ],
            
            # Confirmaciones
            "seller_confirmed": False,
            "buyer_paid": False,
            
            # Notas y comentarios
            "notes": "",
            
            # Método de pago acordado
            "payment_method": "",
            
            # Timestamps
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "expires_at": None,  # Opcionalmente se puede agregar expiración
            "completed_at": None
        }
        
        result = self.collection.insert_one(transaction_data)
        return str(result.inserted_id), transaction_code
    
    def find_by_id(self, transaction_id):
        """Buscar transacción por ID"""
        try:
            return self.collection.find_one({"_id": ObjectId(transaction_id)})
        except:
            return None
    
    def find_by_code(self, transaction_code):
        """Buscar transacción por código"""
        return self.collection.find_one({"transaction_code": transaction_code})
    
    def find_by_product(self, product_id):
        """Obtener transacciones de un producto"""
        return list(self.collection.find({"product_id": product_id}).sort("created_at", -1))
    
    def find_by_buyer(self, buyer_id, skip=0, limit=20):
        """Obtener transacciones donde el usuario es comprador"""
        transactions = self.collection.find({"buyer_id": buyer_id})\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)
        return list(transactions)
    
    def find_by_seller(self, seller_id, skip=0, limit=20):
        """Obtener transacciones donde el usuario es vendedor"""
        transactions = self.collection.find({"seller_id": seller_id})\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)
        return list(transactions)
    
    def update_status(self, transaction_id, new_status, message, user_id):
        """Actualizar estado de la transacción"""
        transaction = self.find_by_id(transaction_id)
        if not transaction:
            return False
        
        # Verificar que el usuario sea parte de la transacción
        if user_id not in [transaction['buyer_id'], transaction['seller_id']]:
            return False
        
        # Agregar evento al timeline
        timeline_event = {
            "status": new_status,
            "timestamp": datetime.utcnow(),
            "message": message,
            "by_user_id": user_id
        }
        
        update_data = {
            "status": new_status,
            "updated_at": datetime.utcnow()
        }
        
        # Si se completa, guardar fecha de completado
        if new_status == self.STATUS['COMPLETED']:
            update_data["completed_at"] = datetime.utcnow()
        
        result = self.collection.update_one(
            {"_id": ObjectId(transaction_id)},
            {
                "$set": update_data,
                "$push": {"timeline": timeline_event}
            }
        )
        
        return result.modified_count > 0
    
    def seller_confirm(self, transaction_id, seller_id, payment_method=""):
        """Vendedor confirma la venta"""
        transaction = self.find_by_id(transaction_id)
        if not transaction or transaction['seller_id'] != seller_id:
            return False
        
        timeline_event = {
            "status": self.STATUS['CONFIRMED'],
            "timestamp": datetime.utcnow(),
            "message": "Vendedor confirmó la venta",
            "by_user_id": seller_id
        }
        
        update_data = {
            "status": self.STATUS['CONFIRMED'],
            "seller_confirmed": True,
            "payment_method": payment_method,
            "updated_at": datetime.utcnow()
        }
        
        result = self.collection.update_one(
            {"_id": ObjectId(transaction_id)},
            {
                "$set": update_data,
                "$push": {"timeline": timeline_event}
            }
        )
        
        return result.modified_count > 0
    
    def buyer_confirm_payment(self, transaction_id, buyer_id):
        """Comprador confirma que realizó el pago"""
        transaction = self.find_by_id(transaction_id)
        if not transaction or transaction['buyer_id'] != buyer_id:
            return False
        
        timeline_event = {
            "status": self.STATUS['PAYMENT_CONFIRMED'],
            "timestamp": datetime.utcnow(),
            "message": "Comprador confirmó el pago",
            "by_user_id": buyer_id
        }
        
        update_data = {
            "status": self.STATUS['PAYMENT_CONFIRMED'],
            "buyer_paid": True,
            "updated_at": datetime.utcnow()
        }
        
        result = self.collection.update_one(
            {"_id": ObjectId(transaction_id)},
            {
                "$set": update_data,
                "$push": {"timeline": timeline_event}
            }
        )
        
        return result.modified_count > 0
    
    def complete_transaction(self, transaction_id, user_id):
        """Marcar transacción como completada"""
        return self.update_status(
            transaction_id, 
            self.STATUS['COMPLETED'], 
            "Transacción completada exitosamente",
            user_id
        )
    
    def cancel_transaction(self, transaction_id, user_id, reason=""):
        """Cancelar una transacción"""
        message = f"Transacción cancelada. Motivo: {reason}" if reason else "Transacción cancelada"
        return self.update_status(
            transaction_id,
            self.STATUS['CANCELLED'],
            message,
            user_id
        )
    
    def add_note(self, transaction_id, user_id, note):
        """Agregar una nota a la transacción"""
        transaction = self.find_by_id(transaction_id)
        if not transaction:
            return False
        
        # Verificar que el usuario sea parte de la transacción
        if user_id not in [transaction['buyer_id'], transaction['seller_id']]:
            return False
        
        note_entry = {
            "timestamp": datetime.utcnow(),
            "user_id": user_id,
            "note": note
        }
        
        result = self.collection.update_one(
            {"_id": ObjectId(transaction_id)},
            {
                "$push": {"timeline": {
                    "status": transaction['status'],
                    "timestamp": datetime.utcnow(),
                    "message": f"Nota agregada: {note}",
                    "by_user_id": user_id
                }},
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        return result.modified_count > 0
    
    def to_dict(self, transaction):
        """Convertir transacción a diccionario"""
        if not transaction:
            return None
        
        return {
            "id": str(transaction["_id"]),
            "transaction_code": transaction.get("transaction_code"),
            "product_id": transaction.get("product_id"),
            "buyer_id": transaction.get("buyer_id"),
            "seller_id": transaction.get("seller_id"),
            "product_snapshot": transaction.get("product_snapshot", {}),
            "status": transaction.get("status"),
            "timeline": transaction.get("timeline", []),
            "seller_confirmed": transaction.get("seller_confirmed", False),
            "buyer_paid": transaction.get("buyer_paid", False),
            "payment_method": transaction.get("payment_method", ""),
            "created_at": transaction.get("created_at").isoformat() if transaction.get("created_at") else None,
            "updated_at": transaction.get("updated_at").isoformat() if transaction.get("updated_at") else None,
            "completed_at": transaction.get("completed_at").isoformat() if transaction.get("completed_at") else None
        }