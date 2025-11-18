from datetime import datetime
from bson import ObjectId

class Product:
    """Modelo de Producto para MongoDB"""
    
    CATEGORIES = ["Remeras", "Abrigos", "Pantalones", "Vestidos", "Calzado", "Accesorios"]
    
    # Estados del producto
    STATUS = {
        'AVAILABLE': 'disponible',      # Disponible para compra
        'RESERVED': 'reservado',         # Reservado (en proceso de venta)
        'SOLD': 'vendido',               # Vendido
        'INACTIVE': 'inactivo'           # Desactivado por el usuario
    }
    
    def __init__(self, db):
        self.collection = db.products
        self._create_indexes()
    
    def _create_indexes(self):
        """Crear índices para búsquedas eficientes"""
        self.collection.create_index("user_id")
        self.collection.create_index("categoria")
        self.collection.create_index("estado")
        self.collection.create_index("created_at")
        self.collection.create_index([("nombre", "text"), ("descripcion", "text")])
    
    def create(self, data, user_id):
        """Crear un nuevo producto"""
        product_data = {
            "nombre": data.get("nombre"),
            "descripcion": data.get("descripcion", ""),
            "costo": float(data.get("costo", 0)),
            "precio": float(data.get("precio", 0)),
            "talla": data.get("talla", ""),
            "categoria": data.get("categoria"),
            "imagen_url": data.get("imagen_url", ""),
            "user_id": user_id,
            "username": data.get("username", ""),
            "estado": self.STATUS['AVAILABLE'],  # Disponible por defecto
            "stock": 1,  # Siempre 1 (producto único de segunda mano)
            "reserved_by": None,  # ID del usuario que lo reservó
            "transaction_id": None,  # ID de la transacción activa
            "views": 0,  # Contador de vistas
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = self.collection.insert_one(product_data)
        return str(result.inserted_id)
    
    def find_all(self, skip=0, limit=20, filters=None):
        """Obtener todos los productos con paginación"""
        query = filters or {}
        
        # Por defecto, solo mostrar productos disponibles
        if "estado" not in query:
            query["estado"] = self.STATUS['AVAILABLE']
        
        products = self.collection.find(query)\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)
        
        return list(products)
    
    def find_by_id(self, product_id):
        """Buscar producto por ID"""
        try:
            return self.collection.find_one({"_id": ObjectId(product_id)})
        except:
            return None
    
    def find_by_user(self, user_id, skip=0, limit=20):
        """Obtener productos de un usuario específico"""
        products = self.collection.find({"user_id": user_id})\
            .sort("created_at", -1)\
            .skip(skip)\
            .limit(limit)
        
        return list(products)
    
    def search(self, query_text, skip=0, limit=20):
        """Buscar productos por texto"""
        products = self.collection.find(
            {
                "$text": {"$search": query_text}, 
                "estado": self.STATUS['AVAILABLE']
            }
        ).skip(skip).limit(limit)
        
        return list(products)
    
    def filter_by_category(self, categoria, skip=0, limit=20):
        """Filtrar productos por categoría"""
        products = self.collection.find(
            {
                "categoria": categoria, 
                "estado": self.STATUS['AVAILABLE']
            }
        ).sort("created_at", -1).skip(skip).limit(limit)
        
        return list(products)
    
    def update(self, product_id, data, user_id):
        """Actualizar un producto (solo el dueño)"""
        update_data = {"updated_at": datetime.utcnow()}
        
        allowed_fields = ["nombre", "descripcion", "precio", "costo", "talla", "categoria", "imagen_url"]
        for field in allowed_fields:
            if field in data:
                if field in ["precio", "costo"]:
                    update_data[field] = float(data[field])
                else:
                    update_data[field] = data[field]
        
        result = self.collection.update_one(
            {"_id": ObjectId(product_id), "user_id": user_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    def delete(self, product_id, user_id):
        """Eliminar un producto (solo el dueño)"""
        result = self.collection.delete_one({
            "_id": ObjectId(product_id),
            "user_id": user_id
        })
        return result.deleted_count > 0
    
    def reserve(self, product_id, buyer_id, transaction_id):
        """
        Reservar un producto para una transacción
        
        Args:
            product_id: ID del producto
            buyer_id: ID del comprador
            transaction_id: ID de la transacción
        
        Returns:
            bool: True si se reservó exitosamente
        """
        product = self.find_by_id(product_id)
        
        # Verificar que esté disponible
        if not product or product['estado'] != self.STATUS['AVAILABLE']:
            return False
        
        # Verificar que el comprador no sea el vendedor
        if product['user_id'] == buyer_id:
            return False
        
        result = self.collection.update_one(
            {
                "_id": ObjectId(product_id),
                "estado": self.STATUS['AVAILABLE']
            },
            {
                "$set": {
                    "estado": self.STATUS['RESERVED'],
                    "reserved_by": buyer_id,
                    "transaction_id": transaction_id,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return result.modified_count > 0
    
    def unreserve(self, product_id):
        """Liberar una reserva (cuando se cancela una transacción)"""
        result = self.collection.update_one(
            {"_id": ObjectId(product_id)},
            {
                "$set": {
                    "estado": self.STATUS['AVAILABLE'],
                    "reserved_by": None,
                    "transaction_id": None,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0
    
    def mark_as_sold(self, product_id, transaction_id):
        """Marcar producto como vendido"""
        result = self.collection.update_one(
            {"_id": ObjectId(product_id)},
            {
                "$set": {
                    "estado": self.STATUS['SOLD'],
                    "stock": 0,
                    "transaction_id": transaction_id,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0
    
    def change_status(self, product_id, status, user_id):
        """Cambiar estado del producto (solo el dueño)"""
        result = self.collection.update_one(
            {"_id": ObjectId(product_id), "user_id": user_id},
            {"$set": {"estado": status, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
    
    def increment_views(self, product_id):
        """Incrementar contador de vistas"""
        self.collection.update_one(
            {"_id": ObjectId(product_id)},
            {"$inc": {"views": 1}}
        )
    
    def count(self, filters=None):
        """Contar productos"""
        query = filters or {}
        return self.collection.count_documents(query)
    
    def to_dict(self, product):
        """Convertir producto a diccionario"""
        if not product:
            return None
        
        return {
            "id": str(product["_id"]),
            "nombre": product.get("nombre"),
            "descripcion": product.get("descripcion", ""),
            "costo": product.get("costo", 0),
            "precio": product.get("precio", 0),
            "talla": product.get("talla", ""),
            "categoria": product.get("categoria"),
            "imagen_url": product.get("imagen_url", ""),
            "user_id": product.get("user_id"),
            "username": product.get("username", ""),
            "estado": product.get("estado", self.STATUS['AVAILABLE']),
            "stock": product.get("stock", 1),
            "reserved_by": product.get("reserved_by"),
            "transaction_id": product.get("transaction_id"),
            "views": product.get("views", 0),
            "created_at": product.get("created_at").isoformat() if product.get("created_at") else None
        }