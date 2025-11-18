from flask import Blueprint, request, jsonify
from middleware.auth_middleware import token_required

transactions_bp = Blueprint('transactions', __name__)

def init_routes(db, transaction_model, product_model, user_model):
    """Inicializar rutas de transacciones"""
    
    @transactions_bp.route('/reserve', methods=['POST'])
    @token_required
    def create_reservation(current_user_id, current_user_role):
        """Crear una reserva (iniciar transacción)"""
        try:
            data = request.get_json()
            product_id = data.get('product_id')
            
            if not product_id:
                return jsonify({
                    'success': False,
                    'message': 'ID de producto requerido'
                }), 400
            
            # Obtener producto
            product = product_model.find_by_id(product_id)
            if not product:
                return jsonify({
                    'success': False,
                    'message': 'Producto no encontrado'
                }), 404
            
            # Verificar que esté disponible
            if product['estado'] != 'disponible':
                return jsonify({
                    'success': False,
                    'message': f'El producto no está disponible. Estado actual: {product["estado"]}'
                }), 400
            
            # Verificar que el comprador no sea el vendedor
            seller_id = product['user_id']
            if current_user_id == seller_id:
                return jsonify({
                    'success': False,
                    'message': 'No puedes comprar tu propio producto'
                }), 400
            
            buyer = user_model.find_by_id(current_user_id)
            seller = user_model.find_by_id(seller_id)
            # Crear transacción
            transaction_id, transaction_code = transaction_model.create(
                product_id=product_id,
                buyer_id=current_user_id,
                seller_id=seller_id,
                product_data=product,
                buyer_data=buyer,
                seller_data=seller  
            )
            
            # Reservar producto
            reserved = product_model.reserve(product_id, current_user_id, transaction_id)
            
            if not reserved:
                return jsonify({
                    'success': False,
                    'message': 'No se pudo reservar el producto'
                }), 400
            
            # Obtener transacción creada
            transaction = transaction_model.find_by_id(transaction_id)
            
            # Obtener datos del vendedor
            seller = user_model.find_by_id(seller_id)
            seller_data = {
                'username': seller.get('username'),
                'nombre': seller.get('nombre'),
                'whatsapp': seller.get('whatsapp', '')
            }
            
            return jsonify({
                'success': True,
                'message': 'Producto reservado exitosamente',
                'data': {
                    'transaction': transaction_model.to_dict(transaction),
                    'seller': seller_data
                }
            }), 201
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error al crear reserva: {str(e)}'
            }), 500
    
    @transactions_bp.route('/<transaction_id>', methods=['GET'])
    @token_required
    def get_transaction(current_user_id, current_user_role, transaction_id):
        """Obtener detalles de una transacción"""
        try:
            transaction = transaction_model.find_by_id(transaction_id)
            
            if not transaction:
                return jsonify({
                    'success': False,
                    'message': 'Transacción no encontrada'
                }), 404
            
            # Verificar que el usuario sea parte de la transacción
            if current_user_id not in [transaction['buyer_id'], transaction['seller_id']]:
                return jsonify({
                    'success': False,
                    'message': 'No tienes acceso a esta transacción'
                }), 403
            
            # Obtener datos del comprador y vendedor
            buyer = user_model.find_by_id(transaction['buyer_id'])
            seller = user_model.find_by_id(transaction['seller_id'])
            
            transaction_data = transaction_model.to_dict(transaction)
            transaction_data['buyer'] = {
                'username': buyer.get('username'),
                'nombre': buyer.get('nombre')
            }
            transaction_data['seller'] = {
                'username': seller.get('username'),
                'nombre': seller.get('nombre'),
                'whatsapp': seller.get('whatsapp', '')
            }
            
            return jsonify({
                'success': True,
                'data': transaction_data
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error al obtener transacción: {str(e)}'
            }), 500
    
    @transactions_bp.route('/code/<transaction_code>', methods=['GET'])
    @token_required
    def get_transaction_by_code(current_user_id, current_user_role, transaction_code):
        """Obtener transacción por código"""
        try:
            transaction = transaction_model.find_by_code(transaction_code)
            
            if not transaction:
                return jsonify({
                    'success': False,
                    'message': 'Transacción no encontrada'
                }), 404
            
            # Verificar acceso
            if current_user_id not in [transaction['buyer_id'], transaction['seller_id']]:
                return jsonify({
                    'success': False,
                    'message': 'No tienes acceso a esta transacción'
                }), 403
            
            return jsonify({
                'success': True,
                'data': transaction_model.to_dict(transaction)
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500
    
    @transactions_bp.route('/my-purchases', methods=['GET'])
    @token_required
    def get_my_purchases(current_user_id, current_user_role):
        """Obtener mis compras"""
        try:
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            skip = (page - 1) * limit
            
            transactions = transaction_model.find_by_buyer(current_user_id, skip, limit)
            transactions_list = [transaction_model.to_dict(t) for t in transactions]
            
            return jsonify({
                'success': True,
                'data': transactions_list
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500
    
    @transactions_bp.route('/my-sales', methods=['GET'])
    @token_required
    def get_my_sales(current_user_id, current_user_role):
        """Obtener mis ventas"""
        try:
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 20))
            skip = (page - 1) * limit
            
            transactions = transaction_model.find_by_seller(current_user_id, skip, limit)
            transactions_list = [transaction_model.to_dict(t) for t in transactions]
            
            return jsonify({
                'success': True,
                'data': transactions_list
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500
    
    @transactions_bp.route('/<transaction_id>/seller-confirm', methods=['POST'])
    @token_required
    def seller_confirm(current_user_id, current_user_role, transaction_id):
        """Vendedor confirma la venta"""
        try:
            data = request.get_json()
            payment_method = data.get('payment_method', '')
            
            transaction = transaction_model.find_by_id(transaction_id)
            
            if not transaction:
                return jsonify({
                    'success': False,
                    'message': 'Transacción no encontrada'
                }), 404
            
            if transaction['seller_id'] != current_user_id:
                return jsonify({
                    'success': False,
                    'message': 'No tienes permiso para confirmar esta venta'
                }), 403
            
            success = transaction_model.seller_confirm(
                transaction_id, 
                current_user_id,
                payment_method
            )
            
            if not success:
                return jsonify({
                    'success': False,
                    'message': 'No se pudo confirmar la venta'
                }), 400
            
            return jsonify({
                'success': True,
                'message': 'Venta confirmada exitosamente'
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500
    
    @transactions_bp.route('/<transaction_id>/buyer-confirm-payment', methods=['POST'])
    @token_required
    def buyer_confirm_payment(current_user_id, current_user_role, transaction_id):
        """Comprador confirma que realizó el pago"""
        try:
            transaction = transaction_model.find_by_id(transaction_id)
            
            if not transaction:
                return jsonify({
                    'success': False,
                    'message': 'Transacción no encontrada'
                }), 404
            
            if transaction['buyer_id'] != current_user_id:
                return jsonify({
                    'success': False,
                    'message': 'No tienes permiso para confirmar este pago'
                }), 403
            
            success = transaction_model.buyer_confirm_payment(transaction_id, current_user_id)
            
            if not success:
                return jsonify({
                    'success': False,
                    'message': 'No se pudo confirmar el pago'
                }), 400
            
            return jsonify({
                'success': True,
                'message': 'Pago confirmado exitosamente'
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500
    
    @transactions_bp.route('/<transaction_id>/complete', methods=['POST'])
    @token_required
    def complete_transaction(current_user_id, current_user_role, transaction_id):
        """Completar una transacción"""
        try:
            transaction = transaction_model.find_by_id(transaction_id)
            
            if not transaction:
                return jsonify({
                    'success': False,
                    'message': 'Transacción no encontrada'
                }), 404
            
            # Verificar que el usuario sea parte de la transacción
            if current_user_id not in [transaction['buyer_id'], transaction['seller_id']]:
                return jsonify({
                    'success': False,
                    'message': 'No tienes permiso para completar esta transacción'
                }), 403
            
            # Verificar que ambas partes hayan confirmado
            if not transaction.get('seller_confirmed') or not transaction.get('buyer_paid'):
                return jsonify({
                    'success': False,
                    'message': 'Ambas partes deben confirmar antes de completar'
                }), 400
            
            # Completar transacción
            success = transaction_model.complete_transaction(transaction_id, current_user_id)
            
            if success:
                # Marcar producto como vendido
                product_model.mark_as_sold(transaction['product_id'], transaction_id)
                
                return jsonify({
                    'success': True,
                    'message': 'Transacción completada exitosamente'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': 'No se pudo completar la transacción'
                }), 400
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500
    
    @transactions_bp.route('/<transaction_id>/cancel', methods=['POST'])
    @token_required
    def cancel_transaction(current_user_id, current_user_role, transaction_id):
        """Cancelar una transacción"""
        try:
            data = request.get_json()
            reason = data.get('reason', '')
            
            transaction = transaction_model.find_by_id(transaction_id)
            
            if not transaction:
                return jsonify({
                    'success': False,
                    'message': 'Transacción no encontrada'
                }), 404
            
            # Verificar que el usuario sea parte de la transacción
            if current_user_id not in [transaction['buyer_id'], transaction['seller_id']]:
                return jsonify({
                    'success': False,
                    'message': 'No tienes permiso para cancelar esta transacción'
                }), 403
            
            # Cancelar transacción
            success = transaction_model.cancel_transaction(transaction_id, current_user_id, reason)
            
            if success:
                # Liberar producto
                product_model.unreserve(transaction['product_id'])
                
                return jsonify({
                    'success': True,
                    'message': 'Transacción cancelada exitosamente'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': 'No se pudo cancelar la transacción'
                }), 400
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500
    
    @transactions_bp.route('/<transaction_id>/note', methods=['POST'])
    @token_required
    def add_note(current_user_id, current_user_role, transaction_id):
        """Agregar una nota a la transacción"""
        try:
            data = request.get_json()
            note = data.get('note', '')
            
            if not note:
                return jsonify({
                    'success': False,
                    'message': 'La nota no puede estar vacía'
                }), 400
            
            success = transaction_model.add_note(transaction_id, current_user_id, note)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': 'Nota agregada exitosamente'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': 'No se pudo agregar la nota'
                }), 400
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500
    
    return transactions_bp