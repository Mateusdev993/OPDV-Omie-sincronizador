import logging
import time
from typing import Dict, List, Any
from services.opdv_service import OPDVService
from services.omie_service import OmieService

class SyncService:
    """Service for synchronizing data between OPDV and Omie"""
    
    def __init__(self, opdv_service: OPDVService, omie_service: OmieService):
        self.opdv_service = opdv_service
        self.omie_service = omie_service
        self.logger = logging.getLogger(__name__)
    
    def sync_data(self, preview_data: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronize data from preview to Omie"""
        try:
            customers = preview_data.get('customers', [])
            orders = preview_data.get('orders', [])
            
            results = {
                'customers': {'success': 0, 'errors': 0, 'messages': []},
                'orders': {'success': 0, 'errors': 0, 'messages': []}
            }
            
            # Only process customers if they were actually selected
            if len(customers) > 0:
                # Sync customers first - filter out customers without valid CPF/CNPJ
                valid_customers = [c for c in customers if c.get('document', '').strip() and c.get('document') not in [None, 'None', 'null', '']]
                skipped_customers = len(customers) - len(valid_customers)
                self.logger.info(f"Processing {len(valid_customers)} valid customers (skipped {skipped_customers} without CPF/CNPJ)")
            else:
                valid_customers = []
                skipped_customers = 0
                self.logger.info("No customers selected for sync - skipping customer processing")
            
            # Initialize tracking variables
            opdv_to_omie_customer_map = {}
            successful_customers = set()
            
            if skipped_customers > 0:
                self.logger.warning(f"Skipping {skipped_customers} customers without CPF/CNPJ")
                results['customers']['messages'].append(f"Skipped {skipped_customers} customers without CPF/CNPJ (Omie requirement)")
            
            self.logger.info(f"Starting customer synchronization: {len(valid_customers)} valid customers")
            for i, customer in enumerate(valid_customers):
                try:
                    # Rate limiting: 1.5 segundos entre requests para evitar 425 (rate limit)
                    if i > 0:
                        time.sleep(1.5)
                        
                    self.logger.debug(f"Syncing customer {i+1}/{len(valid_customers)}: {customer.get('name')} (ID: {customer.get('external_id')}) CPF/CNPJ: {customer.get('document', '')}")
                    
                    # For sync operations, we'll attempt to create customers directly
                    # The Omie API will return appropriate error if customer already exists
                    result = self.omie_service.create_customer(customer)
                    
                    if result['success']:
                        results['customers']['success'] += 1
                        
                        # Check if customer already existed
                        if result.get('already_exists'):
                            results['customers']['messages'].append(
                                f"Customer '{customer.get('name')}' already exists in Omie"
                            )
                        else:
                            results['customers']['messages'].append(
                                f"Customer '{customer.get('name')}' created successfully"
                            )
                        
                        # Track successful customer mapping
                        opdv_id = customer.get('external_id')
                        successful_customers.add(opdv_id)
                        # Use the actual Omie ID returned by the API
                        omie_id = result.get('omie_id', opdv_id)
                        opdv_to_omie_customer_map[opdv_id] = omie_id
                        
                        self.logger.info(f"Customer '{customer.get('name')}' mapped: OPDV {opdv_id} -> Omie {omie_id}")
                    else:
                        results['customers']['errors'] += 1
                        error_msg = f"Failed to process customer '{customer.get('name')}': {result.get('message', 'Unknown error')}"
                        results['customers']['messages'].append(error_msg)
                        self.logger.error(error_msg)
                except Exception as e:
                    results['customers']['errors'] += 1
                    error_msg = f"Error syncing customer '{customer.get('name')}': {str(e)}"
                    results['customers']['messages'].append(error_msg)
                    self.logger.error(error_msg)
            
            # Sync orders - only if orders were selected
            if len(orders) > 0:
                self.logger.info(f"Starting order synchronization: {len(orders)} orders")
            else:
                self.logger.info("No orders selected for sync - skipping order processing")
            for i, order in enumerate(orders):
                try:
                    # Rate limiting: 0.5 segundos entre pedidos para evitar timeout
                    if i > 0:
                        time.sleep(0.5)
                    
                    # Check if order has a valid customer
                    customer_id = order.get('customer_id')
                    if not customer_id:
                        results['orders']['errors'] += 1
                        results['orders']['messages'].append(f"❌ Pedido pulado: ID do cliente não informado")
                        continue
                    
                    # Check if we need customer mapping or if customer already exists in Omie
                    customer_found = False
                    if str(customer_id) in opdv_to_omie_customer_map:
                        omie_customer_id = opdv_to_omie_customer_map[str(customer_id)]
                        order['customer_id'] = omie_customer_id
                        customer_found = True
                        self.logger.debug(f"Using mapped customer ID: OPDV {customer_id} -> Omie {omie_customer_id}")
                    else:
                        # Primeiro, verificar se cliente já existe no Omie pelo ID de integração
                        self.logger.debug(f"Checking if customer {customer_id} already exists in Omie")
                        
                        # Tentar encontrar cliente existente no Omie usando o ID de integração
                        existing_customer = self.omie_service.find_customer_by_integration_id(str(customer_id))
                        
                        if existing_customer.get('success') and existing_customer.get('found'):
                            # Cliente já existe no Omie, usar conta corrente existente
                            omie_customer_id = existing_customer['customer']['omie_id']
                            
                            # Para TODOS os clientes, buscar/criar conta corrente usando a API oficial
                            customer_name = existing_customer['customer'].get('name', f'Cliente {omie_customer_id}')
                            account_result = self.omie_service._create_conta_corrente(omie_customer_id, customer_name)
                            if account_result.get('success'):
                                account_code = account_result.get('account_code', omie_customer_id)
                                self.logger.info(f"Account code for customer {omie_customer_id}: {account_code}")
                            else:
                                account_code = omie_customer_id
                                self.logger.warning(f"Failed to get account code for customer {omie_customer_id}, using customer ID as fallback")
                            
                            opdv_to_omie_customer_map[str(customer_id)] = omie_customer_id
                            order['customer_id'] = omie_customer_id
                            order['account_code'] = account_code
                            customer_found = True
                            self.logger.info(f"Found existing customer in Omie: OPDV {customer_id} -> Omie {omie_customer_id} (Account: {account_code})")
                        else:
                            # Cliente não existe, tentar criar (mas isso não deveria acontecer para pedidos isolados)
                            results['orders']['errors'] += 1
                            error_msg = f"❌ Cliente não encontrado: {customer_id} - Crie o cliente primeiro antes de sincronizar o pedido"
                            results['orders']['messages'].append(error_msg)
                            self.logger.warning(error_msg)
                            continue
                    
                    if not customer_found:
                        results['orders']['errors'] += 1
                        error_msg = f"❌ Cliente não encontrado: {customer_id} - Sincronize o cliente primeiro"
                        results['orders']['messages'].append(error_msg)
                        continue
                    
                    # Customer ID mapping was already handled above
                    
                    # PRIMEIRO: Verificar TODOS os produtos do pedido
                    self.logger.debug(f"Checking all products for order {order.get('order_number')}")
                    products_to_create = []
                    
                    for idx, item in enumerate(order.get('items', []), 1):
                        product_code = item.get('product_integration_code', f"PROD_{order.get('external_id')}_{idx}")
                        product_name = item.get('product_name', f'Produto OPDV {product_code}')
                        
                        # Verificar se produto existe
                        check_result = self.omie_service.check_product_exists(product_code)
                        
                        if check_result.get('exists'):
                            self.logger.info(f"Product already exists: {product_code} (ID: {check_result.get('omie_id')})")
                        else:
                            self.logger.info(f"Product needs to be created: {product_code}")
                            products_to_create.append({
                                'integration_code': product_code,
                                'name': product_name
                            })
                    
                    # SEGUNDO: Criar apenas os produtos que não existem
                    if products_to_create:
                        self.logger.info(f"Creating {len(products_to_create)} missing products...")
                        created_products = []
                        
                        for product_data in products_to_create:
                            product_result = self.omie_service.create_product(product_data)
                            
                            if product_result.get('success'):
                                self.logger.info(f"Product created: {product_data['integration_code']} (ID: {product_result.get('omie_id')})")
                                created_products.append(product_data['integration_code'])
                            else:
                                self.logger.error(f"Failed to create product: {product_data['integration_code']} - {product_result.get('message')}")
                                # This is a critical error - cannot proceed with order if products can't be created
                                self.logger.error(f"Skipping order {order.get('order_number')} due to product creation failure")
                                break  # Skip this order
                        
                        if created_products:
                            # Aguardar sincronização da API após criação de produtos
                            self.logger.info(f"Waiting for API synchronization after creating {len(created_products)} products...")
                            time.sleep(3)
                        
                        # Verificar se conseguimos criar todos os produtos necessários
                        if len(created_products) != len(products_to_create):
                            failed_products = [p['integration_code'] for p in products_to_create if p['integration_code'] not in created_products]
                            self.logger.error(f"Could not create all required products. Missing: {failed_products}")
                            continue  # Skip this order
                    else:
                        self.logger.info("All products already exist for this order")
                    
                    # SEGUNDO: Criar o pedido após garantir que produtos existem
                    self.logger.debug(f"Syncing order {i+1}/{len(orders)}: {order.get('order_number')} (ID: {order.get('external_id')}) Customer: {customer_id}")
                    result = self.omie_service.create_order(order)
                    
                    if result['success']:
                        results['orders']['success'] += 1
                        results['orders']['messages'].append(
                            f"Pedido '{order.get('order_number')}' sincronizado com sucesso"
                        )
                    elif result.get('error_type') == 'product_not_found':
                        # Try to create missing products and retry order
                        missing_product = result.get('missing_product')
                        if missing_product:
                            # Extract product info from order items
                            product_created = False
                            for item in order.get('items', []):
                                if item.get('integration_code') == missing_product:
                                    # Create product first
                                    product_result = self.omie_service.create_product({
                                        'integration_code': missing_product,
                                        'name': item.get('name', 'Produto OPDV')
                                    })
                                    
                                    if product_result['success']:
                                        self.logger.info(f"Product created: {missing_product}")
                                        product_created = True
                                        
                                        # Wait for product to be available
                                        time.sleep(3)
                                        
                                        # Retry order creation
                                        retry_result = self.omie_service.create_order(order)
                                        
                                        if retry_result['success']:
                                            results['orders']['success'] += 1
                                            results['orders']['messages'].append(
                                                f"Pedido '{order.get('order_number')}' sincronizado após criar produto '{item.get('name')}'"
                                            )
                                        else:
                                            results['orders']['errors'] += 1
                                            error_msg = f"Falha ao sincronizar pedido '{order.get('order_number')}' após criar produto: {retry_result['message']}"
                                            results['orders']['messages'].append(error_msg)
                                    else:
                                        results['orders']['errors'] += 1
                                        error_msg = f"Falha ao criar produto '{item.get('name')}' para pedido '{order.get('order_number')}': {product_result['message']}"
                                        results['orders']['messages'].append(error_msg)
                                    break
                            
                            if not product_created:
                                results['orders']['errors'] += 1
                                error_msg = f"Produto não encontrado nos itens do pedido '{order.get('order_number')}'"
                                results['orders']['messages'].append(error_msg)
                        else:
                            results['orders']['errors'] += 1
                            error_msg = f"Código do produto não identificado no erro: {result['message']}"
                            results['orders']['messages'].append(error_msg)
                    else:
                        results['orders']['errors'] += 1
                        error_msg = f"Falha ao sincronizar pedido '{order.get('order_number')}': {result['message']}"
                        results['orders']['messages'].append(error_msg)
                        self.logger.error(error_msg)
                except Exception as e:
                    results['orders']['errors'] += 1
                    error_msg = f"Error syncing order '{order.get('order_number')}': {str(e)}"
                    results['orders']['messages'].append(error_msg)
                    self.logger.error(error_msg)
            
            # Prepare summary
            total_success = results['customers']['success'] + results['orders']['success']
            total_errors = results['customers']['errors'] + results['orders']['errors']
            
            if total_success > 0:
                summary_message = (
                    f"Sincronização concluída com sucesso. "
                    f"Sucessos: {total_success} registros, "
                    f"Erros: {total_errors} registros. "
                    f"Clientes: {results['customers']['success']}/{len(valid_customers)}, "
                    f"Pedidos: {results['orders']['success']}/{len(orders)}"
                )
            else:
                summary_message = (
                    f"Sincronização encontrou problemas. API do Omie pode estar sobrecarregada. "
                    f"Tente novamente com menos registros ou aguarde alguns minutos."
                )
            
            # Prepare detailed results for frontend
            customer_results = []
            for customer in valid_customers:
                customer_results.append({
                    'success': True,
                    'customer_id': customer['external_id'],
                    'name': customer['name'],
                    'omie_id': opdv_to_omie_customer_map.get(customer['external_id'], customer['external_id'])
                })
            
            order_results = []
            # Order results would be populated during order processing
            
            return {
                'success': total_success > 0,
                'message': summary_message,
                'customer_results': customer_results,
                'order_results': order_results,
                'summary': {
                    'customers_processed': len(valid_customers),
                    'customers_created': results['customers']['success'],
                    'customers_errors': results['customers']['errors'],
                    'orders_processed': len(orders) if orders else 0,
                    'orders_created': results['orders']['success'],
                    'orders_errors': results['orders']['errors']
                },
                'details': results
            }
            
        except Exception as e:
            self.logger.error(f"Synchronization error: {str(e)}")
            return {
                'success': False,
                'message': f"Synchronization failed: {str(e)}",
                'details': None
            }
    
    def validate_data(self, preview_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data before synchronization"""
        validation_results = {
            'valid': True,
            'warnings': [],
            'errors': []
        }
        
        customers = preview_data.get('customers', [])
        orders = preview_data.get('orders', [])
        
        # Validate customers
        for i, customer in enumerate(customers):
            if not customer.get('name'):
                validation_results['errors'].append(f"Customer {i+1}: Name is required")
                validation_results['valid'] = False
            
            if not customer.get('document'):
                validation_results['warnings'].append(f"Customer {i+1}: Document is missing")
        
        # Validate orders
        for i, order in enumerate(orders):
            if not order.get('customer_id'):
                validation_results['errors'].append(f"Order {i+1}: Customer ID is required")
                validation_results['valid'] = False
            
            if not order.get('items'):
                validation_results['errors'].append(f"Order {i+1}: Must have at least one item")
                validation_results['valid'] = False
        
        return validation_results
