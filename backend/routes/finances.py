from flask import Blueprint, request, jsonify
from middleware.auth_middleware import token_required  # Solo token_required, NO admin_required
from datetime import datetime, timedelta
from bson import ObjectId

finances_bp = Blueprint('finances', __name__)

def init_routes(db, transaction_model, product_model, user_model):
    """Inicializar rutas de finanzas (sin restricción de admin)"""
    
    @finances_bp.route('/my-finances', methods=['GET'])
    @token_required  # ← Solo autenticación, NO admin
    def get_my_finances(current_user_id, current_user_role):
        """Obtener mis finanzas completas (ventas y compras)"""
        try:
            # Parámetros de filtro
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            categoria = request.args.get('categoria')
            
            # Construir filtro de fechas
            date_filter = {}
            if start_date:
                date_filter['$gte'] = datetime.fromisoformat(start_date)
            if end_date:
                date_filter['$lte'] = datetime.fromisoformat(end_date)
            
            # VENTAS (donde soy vendedor y está completada)
            sales_query = {
                'seller_id': current_user_id,
                'status': 'completada'
            }
            if date_filter:
                sales_query['completed_at'] = date_filter
            
            sales = list(db.transactions.find(sales_query))
            
            # Calcular métricas de ventas
            total_sales_amount = 0
            total_cost = 0
            total_profit = 0
            sales_by_category = {}
            
            for sale in sales:
                product = sale['product_snapshot']
                precio_venta = product.get('precio', 0)
                costo = product.get('costo', 0)
                ganancia = precio_venta - costo
                
                # Si hay filtro de categoría y no coincide, saltar
                if categoria and product.get('categoria') != categoria:
                    continue
                
                total_sales_amount += precio_venta
                total_cost += costo
                total_profit += ganancia
                
                # Agrupar por categoría
                cat = product.get('categoria', 'Sin categoría')
                if cat not in sales_by_category:
                    sales_by_category[cat] = {
                        'count': 0,
                        'total_sales': 0,
                        'total_cost': 0,
                        'total_profit': 0
                    }
                
                sales_by_category[cat]['count'] += 1
                sales_by_category[cat]['total_sales'] += precio_venta
                sales_by_category[cat]['total_cost'] += costo
                sales_by_category[cat]['total_profit'] += ganancia
            
            # COMPRAS (donde soy comprador y está completada)
            purchases_query = {
                'buyer_id': current_user_id,
                'status': 'completada'
            }
            if date_filter:
                purchases_query['completed_at'] = date_filter
            
            purchases = list(db.transactions.find(purchases_query))
            
            total_purchases_amount = 0
            purchases_by_category = {}
            
            for purchase in purchases:
                product = purchase['product_snapshot']
                precio = product.get('precio', 0)
                
                # Si hay filtro de categoría y no coincide, saltar
                if categoria and product.get('categoria') != categoria:
                    continue
                
                total_purchases_amount += precio
                
                # Agrupar por categoría
                cat = product.get('categoria', 'Sin categoría')
                if cat not in purchases_by_category:
                    purchases_by_category[cat] = {
                        'count': 0,
                        'total_amount': 0
                    }
                
                purchases_by_category[cat]['count'] += 1
                purchases_by_category[cat]['total_amount'] += precio
            
            # Calcular margen de ganancia
            margen_porcentaje = 0
            if total_sales_amount > 0:
                margen_porcentaje = (total_profit / total_sales_amount) * 100
            
            # Balance neto
            balance_neto = total_sales_amount - total_purchases_amount
            
            return jsonify({
                'success': True,
                'data': {
                    'sales': {
                        'total_transactions': len(sales),
                        'total_amount': round(total_sales_amount, 2),
                        'total_cost': round(total_cost, 2),
                        'total_profit': round(total_profit, 2),
                        'profit_margin_percentage': round(margen_porcentaje, 2),
                        'by_category': sales_by_category
                    },
                    'purchases': {
                        'total_transactions': len(purchases),
                        'total_amount': round(total_purchases_amount, 2),
                        'by_category': purchases_by_category
                    },
                    'summary': {
                        'net_balance': round(balance_neto, 2),
                        'total_income': round(total_sales_amount, 2),
                        'total_expenses': round(total_purchases_amount + total_cost, 2),
                        'net_profit': round(total_profit, 2)
                    }
                }
            }), 200
            
        except Exception as e:
            print(f"❌ Error en my-finances: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Error al obtener finanzas: {str(e)}'
            }), 500
    
    @finances_bp.route('/sales-history', methods=['GET'])
    @token_required  # ← Solo autenticación, NO admin
    def get_sales_history(current_user_id, current_user_role):
        """Obtener historial detallado de ventas"""
        try:
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 50))
            skip = (page - 1) * limit
            
            # Filtros
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            categoria = request.args.get('categoria')
            
            query = {
                'seller_id': current_user_id,
                'status': 'completada'
            }
            
            # Filtro de fechas
            if start_date or end_date:
                date_filter = {}
                if start_date:
                    date_filter['$gte'] = datetime.fromisoformat(start_date)
                if end_date:
                    date_filter['$lte'] = datetime.fromisoformat(end_date)
                query['completed_at'] = date_filter
            
            # Obtener transacciones
            transactions = list(db.transactions.find(query)
                .sort('completed_at', -1)
                .skip(skip)
                .limit(limit))
            
            # Formatear datos
            sales_list = []
            for t in transactions:
                product = t.get('product_snapshot', {})
                
                # Filtrar por categoría si aplica
                if categoria and product.get('categoria') != categoria:
                    continue
                
                precio_venta = product.get('precio', 0)
                costo = product.get('costo', 0)
                ganancia = precio_venta - costo
                margen = (ganancia / precio_venta * 100) if precio_venta > 0 else 0
                
                sales_list.append({
                    'transaction_id': str(t['_id']),
                    'transaction_code': t.get('transaction_code', 'N/A'),
                    'product_name': product.get('nombre', 'N/A'),
                    'categoria': product.get('categoria', 'Sin categoría'),
                    'precio_venta': precio_venta,
                    'costo': costo,
                    'ganancia': round(ganancia, 2),
                    'margen_porcentaje': round(margen, 2),
                    'buyer_username': t.get('buyer_username', 'N/A'),
                    'completed_at': t['completed_at'].isoformat() if t.get('completed_at') else None,
                    'payment_method': t.get('payment_method', 'N/A')
                })
            
            total = db.transactions.count_documents(query)
            
            return jsonify({
                'success': True,
                'data': {
                    'sales': sales_list,
                    'pagination': {
                        'page': page,
                        'limit': limit,
                        'total': total,
                        'pages': (total + limit - 1) // limit if total > 0 else 0
                    }
                }
            }), 200
            
        except Exception as e:
            print(f"❌ Error en sales-history: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Error al obtener historial de ventas: {str(e)}'
            }), 500
    
    @finances_bp.route('/purchases-history', methods=['GET'])
    @token_required  # ← Solo autenticación, NO admin
    def get_purchases_history(current_user_id, current_user_role):
        """Obtener historial detallado de compras"""
        try:
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 50))
            skip = (page - 1) * limit
            
            # Filtros
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            categoria = request.args.get('categoria')
            
            query = {
                'buyer_id': current_user_id,
                'status': 'completada'
            }
            
            # Filtro de fechas
            if start_date or end_date:
                date_filter = {}
                if start_date:
                    date_filter['$gte'] = datetime.fromisoformat(start_date)
                if end_date:
                    date_filter['$lte'] = datetime.fromisoformat(end_date)
                query['completed_at'] = date_filter
            
            # Obtener transacciones
            transactions = list(db.transactions.find(query)
                .sort('completed_at', -1)
                .skip(skip)
                .limit(limit))
            
            # Formatear datos
            purchases_list = []
            for t in transactions:
                product = t.get('product_snapshot', {})
                
                # Filtrar por categoría si aplica
                if categoria and product.get('categoria') != categoria:
                    continue
                
                purchases_list.append({
                    'transaction_id': str(t['_id']),
                    'transaction_code': t.get('transaction_code', 'N/A'),
                    'product_name': product.get('nombre', 'N/A'),
                    'categoria': product.get('categoria', 'Sin categoría'),
                    'precio': product.get('precio', 0),
                    'seller_username': t.get('seller_username', 'N/A'),
                    'completed_at': t['completed_at'].isoformat() if t.get('completed_at') else None,
                    'payment_method': t.get('payment_method', 'N/A')
                })
            
            total = db.transactions.count_documents(query)
            
            return jsonify({
                'success': True,
                'data': {
                    'purchases': purchases_list,
                    'pagination': {
                        'page': page,
                        'limit': limit,
                        'total': total,
                        'pages': (total + limit - 1) // limit if total > 0 else 0
                    }
                }
            }), 200
            
        except Exception as e:
            print(f"❌ Error en purchases-history: {str(e)}")
            return jsonify({
                'success': False,
                'message': f'Error al obtener historial de compras: {str(e)}'
            }), 500
    
    return finances_bp