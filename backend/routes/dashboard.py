from flask import Blueprint, jsonify
from middleware.auth_middleware import admin_required
from datetime import datetime, timedelta
from bson import ObjectId

dashboard_bp = Blueprint('dashboard', __name__)

def init_routes(db, product_model, user_model):
    """Inicializar rutas del dashboard"""
    
    @dashboard_bp.route('/stats', methods=['GET'])
    @admin_required
    def get_stats(current_user_id, current_user_role):
        """Obtener estadísticas generales"""
        try:
            # Contar usuarios totales
            total_users = db.users.count_documents({})
            active_users = db.users.count_documents({'active': True})
            
            # Contar productos
            total_products = db.products.count_documents({})
            available_products = db.products.count_documents({'estado': 'disponible'})
            sold_products = db.products.count_documents({'estado': 'vendido'})
            
            # Usuarios registrados en los últimos 30 días
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            new_users = db.users.count_documents({
                'created_at': {'$gte': thirty_days_ago}
            })
            
            # Productos publicados en los últimos 30 días
            new_products = db.products.count_documents({
                'created_at': {'$gte': thirty_days_ago}
            })
            
            return jsonify({
                'success': True,
                'data': {
                    'users': {
                        'total': total_users,
                        'active': active_users,
                        'new_last_30_days': new_users
                    },
                    'products': {
                        'total': total_products,
                        'available': available_products,
                        'sold': sold_products,
                        'new_last_30_days': new_products
                    }
                }
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error al obtener estadísticas: {str(e)}'
            }), 500
    
    @dashboard_bp.route('/products-by-category', methods=['GET'])
    @admin_required
    def products_by_category(current_user_id, current_user_role):
        """Obtener productos agrupados por categoría"""
        try:
            pipeline = [
                {'$group': {
                    '_id': '$categoria',
                    'total': {'$sum': 1},
                    'disponibles': {
                        '$sum': {'$cond': [{'$eq': ['$estado', 'disponible']}, 1, 0]}
                    }
                }},
                {'$sort': {'total': -1}}
            ]
            
            result = list(db.products.aggregate(pipeline))
            
            # Formatear resultado
            data = [{
                'categoria': item['_id'],
                'total': item['total'],
                'disponibles': item['disponibles']
            } for item in result]
            
            return jsonify({
                'success': True,
                'data': data
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error al obtener productos por categoría: {str(e)}'
            }), 500
    
    @dashboard_bp.route('/recent-activity', methods=['GET'])
    @admin_required
    def recent_activity(current_user_id, current_user_role):
        """Obtener actividad reciente"""
        try:
            # Últimos 10 usuarios registrados
            recent_users = list(db.users.find()
                .sort('created_at', -1)
                .limit(10))
            
            # Últimos 10 productos publicados
            recent_products = list(db.products.find()
                .sort('created_at', -1)
                .limit(10))
            
            # Formatear usuarios
            users_list = [{
                'id': str(u['_id']),
                'username': u.get('username'),
                'email': u.get('email'),
                'created_at': u.get('created_at').isoformat() if u.get('created_at') else None
            } for u in recent_users]
            
            # Formatear productos
            products_list = [product_model.to_dict(p) for p in recent_products]
            
            return jsonify({
                'success': True,
                'data': {
                    'recent_users': users_list,
                    'recent_products': products_list
                }
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error al obtener actividad reciente: {str(e)}'
            }), 500
    
    @dashboard_bp.route('/users-growth', methods=['GET'])
    @admin_required
    def users_growth(current_user_id, current_user_role):
        """Obtener crecimiento de usuarios por mes"""
        try:
            pipeline = [
                {'$group': {
                    '_id': {
                        'year': {'$year': '$created_at'},
                        'month': {'$month': '$created_at'}
                    },
                    'count': {'$sum': 1}
                }},
                {'$sort': {'_id.year': 1, '_id.month': 1}},
                {'$limit': 12}
            ]
            
            result = list(db.users.aggregate(pipeline))
            
            # Formatear resultado
            months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 
                     'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            
            data = [{
                'month': f"{months[item['_id']['month']-1]} {item['_id']['year']}",
                'count': item['count']
            } for item in result]
            
            return jsonify({
                'success': True,
                'data': data
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error al obtener crecimiento de usuarios: {str(e)}'
            }), 500
    
    @dashboard_bp.route('/top-sellers', methods=['GET'])
    @admin_required
    def top_sellers(current_user_id, current_user_role):
        """Obtener usuarios con más productos publicados"""
        try:
            pipeline = [
                {'$group': {
                    '_id': '$user_id',
                    'username': {'$first': '$username'},
                    'total_products': {'$sum': 1},
                    'available': {
                        '$sum': {'$cond': [{'$eq': ['$estado', 'disponible']}, 1, 0]}
                    }
                }},
                {'$sort': {'total_products': -1}},
                {'$limit': 10}
            ]
            
            result = list(db.products.aggregate(pipeline))
            
            # Formatear resultado
            data = [{
                'user_id': item['_id'],
                'username': item['username'],
                'total_products': item['total_products'],
                'available': item['available']
            } for item in result]
            
            return jsonify({
                'success': True,
                'data': data
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error al obtener top sellers: {str(e)}'
            }), 500
    
    @dashboard_bp.route('/price-stats', methods=['GET'])
    @admin_required
    def price_stats(current_user_id, current_user_role):
        """Obtener estadísticas de precios"""
        try:
            pipeline = [
                {'$group': {
                    '_id': None,
                    'avg_price': {'$avg': '$precio'},
                    'min_price': {'$min': '$precio'},
                    'max_price': {'$max': '$precio'}
                }}
            ]
            
            result = list(db.products.aggregate(pipeline))
            
            if result:
                data = {
                    'average': round(result[0]['avg_price'], 2),
                    'minimum': result[0]['min_price'],
                    'maximum': result[0]['max_price']
                }
            else:
                data = {
                    'average': 0,
                    'minimum': 0,
                    'maximum': 0
                }
            
            return jsonify({
                'success': True,
                'data': data
            }), 200
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error al obtener estadísticas de precios: {str(e)}'
            }), 500
            

    @dashboard_bp.route('/financial-summary', methods=['GET'])
    @admin_required
    def financial_summary(current_user_id, current_user_role):
        """Resumen financiero general de la plataforma"""
        try:
            # Todas las transacciones completadas
            completed_transactions = list(db.transactions.find({'status': 'completada'}))

            # Calcular métricas
            total_revenue = 0
            total_cost = 0
            total_profit = 0
            transactions_count = len(completed_transactions)

            for t in completed_transactions:
                product = t['product_snapshot']
                revenue = product.get('precio', 0)
                cost = product.get('costo', 0)

                total_revenue += revenue
                total_cost += cost
                total_profit += (revenue - cost)

            # Promedio de margen de ganancia
            avg_margin = 0
            if total_revenue > 0:
                avg_margin = (total_profit / total_revenue) * 100

            # Vendedor top
            pipeline = [
                {'$match': {'status': 'completada'}},
                {'$group': {
                    '_id': '$seller_id',
                    'total_sales': {'$sum': '$product_snapshot.precio'},
                    'total_transactions': {'$sum': 1},
                    'total_profit': {
                        '$sum': {
                            '$subtract': ['$product_snapshot.precio', '$product_snapshot.costo']
                        }
                    }
                }},
                {'$sort': {'total_profit': -1}},
                {'$limit': 1}
            ]

            top_seller_data = list(db.transactions.aggregate(pipeline))
            top_seller = None

            if top_seller_data:
                seller_id = top_seller_data[0]['_id']
                seller = db.users.find_one({'_id': seller_id})
                top_seller = {
                    'username': seller.get('username') if seller else 'Unknown',
                    'total_sales': top_seller_data[0]['total_sales'],
                    'total_transactions': top_seller_data[0]['total_transactions'],
                    'total_profit': top_seller_data[0]['total_profit']
                }

            return jsonify({
                'success': True,
                'data': {
                    'total_transactions': transactions_count,
                    'total_revenue': round(total_revenue, 2),
                    'total_cost': round(total_cost, 2),
                    'total_profit': round(total_profit, 2),
                    'average_margin_percentage': round(avg_margin, 2),
                    'top_seller': top_seller
                }
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error al obtener resumen financiero: {str(e)}'
            }), 500

    @dashboard_bp.route('/profit-by-category', methods=['GET'])
    @admin_required
    def profit_by_category(current_user_id, current_user_role):
        """Ganancia por categoría"""
        try:
            pipeline = [
                {'$match': {'status': 'completada'}},
                {'$group': {
                    '_id': '$product_snapshot.categoria',
                    'total_revenue': {'$sum': '$product_snapshot.precio'},
                    'total_cost': {'$sum': '$product_snapshot.costo'},
                    'count': {'$sum': 1}
                }},
                {'$project': {
                    'categoria': '$_id',
                    'total_revenue': 1,
                    'total_cost': 1,
                    'total_profit': {'$subtract': ['$total_revenue', '$total_cost']},
                    'count': 1,
                    'avg_margin': {
                        '$multiply': [
                            {'$divide': [
                                {'$subtract': ['$total_revenue', '$total_cost']},
                                '$total_revenue'
                            ]},
                            100
                        ]
                    }
                }},
                {'$sort': {'total_profit': -1}}
            ]

            result = list(db.transactions.aggregate(pipeline))

            data = [{
                'categoria': item['categoria'],
                'total_revenue': round(item['total_revenue'], 2),
                'total_cost': round(item['total_cost'], 2),
                'total_profit': round(item['total_profit'], 2),
                'count': item['count'],
                'avg_margin_percentage': round(item.get('avg_margin', 0), 2)
            } for item in result]

            return jsonify({
                'success': True,
                'data': data
            }), 200

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500      

    return dashboard_bp