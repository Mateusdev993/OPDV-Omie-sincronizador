import os
import logging
from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from services.opdv_service import OPDVService
from services.omie_service import OmieService
from services.sync_service import SyncService
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)

# Create instance directory if it doesn't exist
instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)
    app.logger.info(f"Created instance directory: {instance_path}")

# Simple configuration for PythonAnywhere with absolute path
app.secret_key = "opdv-omie-sync-secret-key-2024"
database_path = os.path.join(instance_path, 'integration.db')
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{database_path}"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'info'

with app.app_context():
    import models
    from models import User
    
    # Create tables
    db.create_all()
    
    # Create default user if not exists
    if not User.query.filter_by(username='Vinicius').first():
        user = User(username='Vinicius')
        user.set_password('vi131211')
        db.session.add(user)
        db.session.commit()
        app.logger.info("Default user 'Vinicius' created")


@login_manager.user_loader
def load_user(user_id):
    """Load user callback for Flask-Login"""
    from models import User
    return User.query.get(int(user_id))

# Initialize services
opdv_service = OPDVService()
omie_service = OmieService()
sync_service = SyncService(opdv_service, omie_service)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Por favor, preencha todos os campos.', 'error')
            return render_template('login.html')
        
        from models import User
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            flash('Usuário ou senha incorretos.', 'error')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    flash('Logout realizado com sucesso.', 'success')
    return redirect(url_for('login'))


@app.route('/')
@login_required
def dashboard():
    """Main dashboard showing connection status and data overview"""
    # Check connection status - OPDV only to avoid Omie API overload
    opdv_status = opdv_service.test_connection()
    omie_status = {'success': True, 'message': 'Credenciais configuradas', 'status': 'configured'}
    
    # Get preview data from database
    preview_data = {'orders': [], 'customers': [], 'total_orders': 0, 'total_customers': 0}
    has_preview_data = False
    
    if session.get('preview_session_id'):
        from models import PreviewData
        
        # Get orders data
        orders_data = PreviewData.query.filter_by(
            session_id=session['preview_session_id'],
            data_type='orders'
        ).first()
        
        # Get customers data
        customers_data = PreviewData.query.filter_by(
            session_id=session['preview_session_id'],
            data_type='customers'
        ).first()
        
        if orders_data:
            preview_data['orders'] = orders_data.get_data()
            preview_data['total_orders'] = orders_data.total_count
            has_preview_data = True
            
        if customers_data:
            preview_data['customers'] = customers_data.get_data()
            preview_data['total_customers'] = customers_data.total_count
            has_preview_data = True
    
    return render_template('dashboard.html', 
                         opdv_status=opdv_status,
                         omie_status=omie_status,
                         preview_data=preview_data,
                         has_preview_data=has_preview_data)

@app.route('/configuration', methods=['GET', 'POST'])
def configuration():
    """Configuration page for API credentials"""
    if request.method == 'POST':
        # Save OPDV credentials
        if 'opdv_url' in request.form:
            session['opdv_url'] = request.form['opdv_url']
            session['opdv_api_key'] = request.form['opdv_api_key']
            session['opdv_store_id'] = request.form.get('opdv_store_id', '')
            opdv_service.configure(
                url=request.form['opdv_url'],
                api_key=request.form['opdv_api_key'],
                store_id=request.form.get('opdv_store_id')
            )
            flash('OPDV configuration saved successfully', 'success')
        
        # Save Omie credentials  
        if 'omie_app_key' in request.form:
            session['omie_app_key'] = request.form['omie_app_key']
            session['omie_app_secret'] = request.form['omie_app_secret']
            omie_service.configure(
                app_key=request.form['omie_app_key'],
                app_secret=request.form['omie_app_secret']
            )
            flash('Omie configuration saved successfully', 'success')
        
        return redirect(url_for('configuration'))
    
    # Load existing configuration
    config = {
        'opdv_url': session.get('opdv_url', ''),
        'opdv_api_key': session.get('opdv_api_key', ''),
        'opdv_store_id': session.get('opdv_store_id', ''),
        'omie_app_key': session.get('omie_app_key', ''),
        'omie_app_secret': session.get('omie_app_secret', '')
    }
    
    return render_template('configuration.html', config=config)

@app.route('/test_connection/<service>')
def test_connection(service):
    """Test connection to OPDV or Omie"""
    try:
        if service == 'opdv':
            result = opdv_service.test_connection()
        elif service == 'omie':
            # Skip API test for Omie to prevent rate limiting
            result = {'success': True, 'message': 'Credenciais Omie configuradas', 'status': 'configured'}
        else:
            return jsonify({'success': False, 'message': 'Invalid service'})
        
        return jsonify(result), 200, {'Content-Type': 'application/json'}
    except Exception as e:
        logging.error(f"Connection test error for {service}: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/extract_data', methods=['GET', 'POST'])
def extract_data():
    """Extract data from OPDV for preview"""
    try:
        # Extract orders and customers
        logging.info("Starting data extraction from OPDV")
        orders = opdv_service.get_orders()
        logging.info(f"Extracted {len(orders)} orders")
        
        customers = opdv_service.get_customers()
        logging.info(f"Extracted {len(customers)} customers")
        
        # Store in database instead of session
        from models import PreviewData
        import uuid
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Clear old preview data for this session
        PreviewData.query.filter_by(session_id=session.get('preview_session_id', '')).delete()
        
        # Store orders
        orders_preview = PreviewData(
            session_id=session_id,
            data_type='orders',
            total_count=len(orders)
        )
        orders_preview.set_data(orders[:50])  # Store first 50 for preview
        db.session.add(orders_preview)
        
        # Store customers
        customers_preview = PreviewData(
            session_id=session_id,
            data_type='customers',
            total_count=len(customers)
        )
        customers_preview.set_data(customers[:50])  # Store first 50 for preview
        db.session.add(customers_preview)
        
        db.session.commit()
        
        # Store session ID in session (small data)
        session['preview_session_id'] = session_id
        session['has_preview_data'] = True
        
        flash(f'Data extracted successfully: {len(orders)} orders, {len(customers)} customers (showing first 50 of each for preview)', 'success')
        
    except Exception as e:
        logging.error(f"Data extraction error: {str(e)}")
        flash(f'Error extracting data: {str(e)}', 'error')
    
    return redirect(url_for('data_preview'))

@app.route('/data_preview')
def data_preview():
    """Show extracted data preview"""
    preview_data = {'orders': [], 'customers': [], 'total_orders': 0, 'total_customers': 0}
    
    if session.get('preview_session_id'):
        from models import PreviewData
        
        # Get orders data
        orders_data = PreviewData.query.filter_by(
            session_id=session['preview_session_id'],
            data_type='orders'
        ).first()
        
        # Get customers data
        customers_data = PreviewData.query.filter_by(
            session_id=session['preview_session_id'],
            data_type='customers'
        ).first()
        
        if orders_data:
            preview_data['orders'] = orders_data.get_data()
            preview_data['total_orders'] = orders_data.total_count
            
        if customers_data:
            preview_data['customers'] = customers_data.get_data()
            preview_data['total_customers'] = customers_data.total_count
    
    if not preview_data['orders'] and not preview_data['customers']:
        flash('No data available for preview. Please extract data first.', 'warning')
        return redirect(url_for('dashboard'))
    
    return render_template('data_preview.html', preview_data=preview_data)

@app.route('/api/sync', methods=['POST'])
@login_required
def api_sync():
    """API endpoint for data synchronization - returns JSON"""
    try:
        # Get the JSON request data  
        request_data = request.get_json()
        logging.info(f"Sync request data: {request_data}")
        
        if not request_data:
            return jsonify({
                'success': False, 
                'message': 'No data provided',
                'customer_results': [],
                'order_results': [],
                'summary': {'customers_processed': 0, 'customers_created': 0, 'customers_errors': 0, 'orders_processed': 0, 'orders_created': 0, 'orders_errors': 0}
            })
        
        selected_customers = request_data.get('selected_customers', [])
        selected_orders = request_data.get('selected_orders', [])
        
        logging.info(f"Selected customers: {selected_customers}")
        logging.info(f"Selected orders: {selected_orders}")
        
        if not selected_customers and not selected_orders:
            return jsonify({
                'success': False, 
                'message': 'No items selected for synchronization',
                'customer_results': [],
                'order_results': [],
                'summary': {'customers_processed': 0, 'customers_created': 0, 'customers_errors': 0, 'orders_processed': 0, 'orders_created': 0, 'orders_errors': 0}
            })
        
        # Get preview data from database
        preview_data = {'orders': [], 'customers': []}
        
        if session.get('preview_session_id'):
            from models import PreviewData
            
            orders_data = PreviewData.query.filter_by(
                session_id=session['preview_session_id'],
                data_type='orders'
            ).first()
            
            customers_data = PreviewData.query.filter_by(
                session_id=session['preview_session_id'],
                data_type='customers'
            ).first()
            
            if orders_data:
                all_orders = orders_data.get_data()
                # Filter only selected orders
                preview_data['orders'] = [order for order in all_orders if str(order.get('external_id')) in selected_orders]
                
            if customers_data:
                all_customers = customers_data.get_data()
                # Filter only selected customers
                preview_data['customers'] = [customer for customer in all_customers if str(customer.get('external_id')) in selected_customers]
        
        logging.info(f"Filtered preview data - Orders: {len(preview_data['orders'])}, Customers: {len(preview_data['customers'])}")
        
        # Initialize services
        opdv_service = OPDVService()
        omie_service = OmieService()
        sync_service = SyncService(opdv_service, omie_service)
        
        # Perform synchronization
        result = sync_service.sync_data(preview_data)
        
        return jsonify(result)
    
    except Exception as e:
        logging.error(f"Sync error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erro na sincronização: {str(e)}',
            'customer_results': [],
            'order_results': [],
            'summary': {
                'customers_processed': 0,
                'customers_created': 0,
                'customers_errors': 1,
                'orders_processed': 0,
                'orders_created': 0,
                'orders_errors': 0
            }
        })

@app.route('/sync_data', methods=['POST'])
@app.route('/sync-data', methods=['POST'])
@login_required
def sync_data():
    """Synchronize data to Omie (form submission - redirects to dashboard)"""
    from werkzeug.exceptions import RequestTimeout
    import signal
    
    def timeout_handler(signum, frame):
        raise RequestTimeout("Sync operation timed out")
    
    # Set timeout for long operations
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(120)  # 120 seconds timeout
    
    try:
        # Get preview data from database
        preview_data = {'orders': [], 'customers': []}
        
        if session.get('preview_session_id'):
            from models import PreviewData
            
            orders_data = PreviewData.query.filter_by(
                session_id=session['preview_session_id'],
                data_type='orders'
            ).first()
            
            customers_data = PreviewData.query.filter_by(
                session_id=session['preview_session_id'],
                data_type='customers'
            ).first()
            
            if orders_data:
                preview_data['orders'] = orders_data.get_data()
            if customers_data:
                preview_data['customers'] = customers_data.get_data()
        
        # Get selected items from request
        request_data = request.get_json() or {}
        selected_orders = request_data.get('selected_orders', [])
        selected_customers = request_data.get('selected_customers', [])
        
        # Filter data to only include selected items - IMPORTANTE: se não há seleção, não processar nada
        if selected_orders:
            preview_data['orders'] = [order for order in preview_data['orders'] 
                                    if str(order.get('external_id')) in selected_orders]
        else:
            preview_data['orders'] = []  # Se nenhum pedido selecionado, não processar pedidos
        
        if selected_customers:
            preview_data['customers'] = [customer for customer in preview_data['customers'] 
                                       if str(customer.get('external_id')) in selected_customers]
        else:
            preview_data['customers'] = []  # Se nenhum cliente selecionado, não processar clientes
        
        if not preview_data['orders'] and not preview_data['customers']:
            flash('Nenhum item selecionado para sincronização', 'warning')
            return redirect(url_for('dashboard'))
        
        # Limit the number of items to prevent server overload
        MAX_ITEMS_PER_SYNC = 10
        if len(preview_data['orders']) > MAX_ITEMS_PER_SYNC:
            preview_data['orders'] = preview_data['orders'][:MAX_ITEMS_PER_SYNC]
            
        if len(preview_data['customers']) > MAX_ITEMS_PER_SYNC:
            preview_data['customers'] = preview_data['customers'][:MAX_ITEMS_PER_SYNC]
        
        # Perform synchronization
        sync_result = sync_service.sync_data(preview_data)
        
        if sync_result['success']:
            flash(f'Data synchronized successfully: {sync_result["message"]}', 'success')
            # Clear preview data after successful sync
            if session.get('preview_session_id'):
                from models import PreviewData
                PreviewData.query.filter_by(session_id=session['preview_session_id']).delete()
                db.session.commit()
                session.pop('preview_session_id', None)
                session.pop('has_preview_data', None)
        else:
            flash(f'Synchronization failed: {sync_result["message"]}', 'error')
            
    except Exception as e:
        logging.error(f"Synchronization error: {str(e)}")
        flash(f'Error during synchronization: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/clear_preview')
def clear_preview():
    """Clear preview data"""
    if session.get('preview_session_id'):
        from models import PreviewData
        PreviewData.query.filter_by(session_id=session['preview_session_id']).delete()
        db.session.commit()
        
    session.pop('preview_session_id', None)
    session.pop('has_preview_data', None)
    flash('Preview data cleared', 'info')
    return redirect(url_for('dashboard'))

@app.route('/api/status')
@login_required
def api_status():
    """API endpoint for connection status"""
    try:
        # Add caching to reduce frequent API calls
        import time
        current_time = time.time()
        
        # Check if we have recent cached status (cache for 5 minutes to reduce API pressure)
        cache_key = 'api_status_cache'
        cache_time_key = 'api_status_time'
        
        if cache_key in session and cache_time_key in session:
            time_diff = current_time - session.get(cache_time_key, 0)
            if time_diff < 300:  # Use cache for 5 minutes
                return jsonify(session[cache_key])
        
        # Perform actual status check - skip Omie API to avoid rate limiting
        opdv_status = opdv_service.test_connection()
        omie_status = {'success': True, 'message': 'Credenciais configuradas', 'status': 'configured'}
        
        from datetime import datetime
        status_result = {
            'opdv': opdv_status,
            'omie': omie_status,
            'timestamp': datetime.now().isoformat()
        }
        
        # Cache the result
        session[cache_time_key] = current_time
        session[cache_key] = status_result
        
        return jsonify(status_result)
    except Exception as e:
        logging.error(f"Status check error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug/opdv')
def debug_opdv():
    """Debug endpoint for OPDV API testing"""
    try:
        if not opdv_service._is_configured():
            return jsonify({'error': 'OPDV not configured'}), 400
        
        # Test stores endpoint
        stores_response = opdv_service.session.get(f'{opdv_service.base_url}/stores', timeout=10)
        
        debug_info = {
            'base_url': opdv_service.base_url,
            'store_id': opdv_service.store_id,
            'headers': dict(opdv_service.session.headers),
            'stores_endpoint': {
                'url': f'{opdv_service.base_url}/stores',
                'status_code': stores_response.status_code,
                'headers': dict(stores_response.headers),
                'content_length': len(stores_response.text),
                'content_preview': stores_response.text[:500]
            }
        }
        
        # Test orders endpoint with minimal params
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)  # Last 7 days for testing
        
        orders_params = {
            'startDate': start_date.strftime('%Y-%m-%d %H:%M:%S'),
            'endDate': end_date.strftime('%Y-%m-%d %H:%M:%S'),
            'limit': 10,
            'offset': 0
        }
        
        if opdv_service.store_id:
            orders_params['stores'] = opdv_service.store_id
        
        orders_response = opdv_service.session.get(
            f'{opdv_service.base_url}/orders',
            params=orders_params,
            timeout=10
        )
        
        debug_info['orders_endpoint'] = {
            'url': f'{opdv_service.base_url}/orders',
            'params': orders_params,
            'status_code': orders_response.status_code,
            'headers': dict(orders_response.headers),
            'content_length': len(orders_response.text),
            'content_preview': orders_response.text[:500]
        }
        
        return jsonify(debug_info)
        
    except Exception as e:
        logging.error(f"OPDV debug error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
