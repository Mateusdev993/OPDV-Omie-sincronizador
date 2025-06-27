import requests
import logging
import os
import time
from typing import Dict, List, Any
from datetime import datetime, timezone


class OPDVService:
    """Service for interacting with OPDV API"""

    def __init__(self):
        self.base_url = None
        self.api_key = None
        self.store_id = None
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)

    def configure(self, url: str, api_key: str, store_id: str = None):
        """Configure OPDV connection"""
        self.base_url = url.rstrip('/')
        self.api_key = api_key
        self.store_id = store_id

        # OPDV uses x-access-token header for authentication
        self.session.headers.update({
            'x-access-token': api_key,
            'Content-Type': 'application/json'
        })
        self.logger.info(
            f"OPDV service configured for URL: {self.base_url} (Store ID: {store_id})"
        )

    def test_connection(self) -> Dict[str, Any]:
        """Test connection to OPDV API"""
        if not self.base_url or not self.api_key:
            # Try to get from environment variables
            env_url = os.getenv('OPDV_URL', 'https://api.opdv.com.br')
            env_api_key = os.getenv('OPDV_TOKEN')
            env_store_id = os.getenv('OPDV_STORE_ID')

            if not env_url or not env_api_key:
                return {
                    'success': False,
                    'message': 'OPDV credentials not configured. Please set OPDV_TOKEN and OPDV_STORE_ID',
                    'status': 'not_configured'
                }

            self.configure(env_url, env_api_key, env_store_id)

        try:
            # Test endpoint using OPDV stores endpoint to validate connection
            response = self.session.get(f'{self.base_url}/stores', timeout=10)

            self.logger.debug(
                f"OPDV test response status: {response.status_code}")
            self.logger.debug(
                f"OPDV test response content: {response.text[:200]}")

            if response.status_code == 200:
                # Try to parse JSON to ensure it's valid
                try:
                    if response.text.strip():
                        response.json()
                    return {
                        'success': True,
                        'message': 'Connection successful',
                        'status': 'connected',
                        'response_time': response.elapsed.total_seconds()
                    }
                except ValueError:
                    return {
                        'success': False,
                        'message':
                        f'Connection successful but invalid JSON response: {response.text[:100]}',
                        'status': 'warning'
                    }
            else:
                return {
                    'success': False,
                    'message':
                    f'HTTP {response.status_code}: {response.text[:200]}',
                    'status': 'error'
                }

        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'message': 'Connection refused - check URL and network',
                'status': 'connection_error'
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'message': 'Connection timeout',
                'status': 'timeout'
            }
        except Exception as e:
            self.logger.error(f"OPDV connection test error: {str(e)}")
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}',
                'status': 'error'
            }

    def get_orders(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Extract orders from OPDV with increased limits and recent data"""
        if not self._is_configured():
            raise Exception("OPDV service not configured")

        try:
            # Use current date range for orders - expanded to 60 days
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=60)  # Last 60 days for more recent data

            # Fetch multiple batches to get more data (API limit is 100 per request)
            all_orders = []
            offset = 0
            max_requests = min(5, (limit // 100) + 1)  # Max 5 requests to get up to 500 orders
            
            for batch in range(max_requests):
                params = {
                    'startDate': start_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'endDate': end_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'limit': 100,  # API max is 100 per request
                    'offset': offset,
                    'includeProducts': 1,  # Incluir detalhes dos produtos
                    'includeCustomer': 1,  # Incluir dados do cliente
                    'includePayments': 1  # Incluir formas de pagamento
                }

                if self.store_id:
                    params['stores'] = self.store_id

                self.logger.debug(f"Fetching batch {batch + 1} with offset {offset}, limit: {params['limit']}")

                try:
                    response = self.session.get(f'{self.base_url}/orders',
                                                params=params,
                                                timeout=30)
                    
                    # Handle rate limiting (425 Too Early)
                    if response.status_code == 425:
                        self.logger.warning(f"Rate limited on batch {batch + 1}, waiting 3 seconds...")
                        time.sleep(3)
                        continue  # Skip this batch and continue with next
                    
                    response.raise_for_status()
                    
                except requests.exceptions.RequestException as e:
                    if batch == 0:
                        # If first batch fails completely, re-raise
                        raise Exception(f"Failed to fetch orders from OPDV: {e}")
                    else:
                        # If subsequent batch fails, continue with what we have
                        self.logger.warning(f"Failed to fetch batch {batch + 1}, continuing with {len(all_orders)} orders")
                        continue

                # Log response details for debugging
                self.logger.debug(f"OPDV orders response status: {response.status_code}")
                self.logger.debug(f"OPDV orders response content: {response.text[:500]}")

                # Handle empty response
                if not response.text.strip():
                    self.logger.info(f"Empty response in batch {batch + 1}")
                    continue

                # Handle response format according to official API documentation
                # Response format: [{"total": number, "orders": []}]
                try:
                    data = response.json()
                except ValueError as e:
                    self.logger.error(f"Failed to parse JSON response: {response.text[:200]}")
                    continue
                
                if isinstance(data, list) and len(data) > 0:
                    # Extract orders from the first result object
                    result = data[0]
                    if isinstance(result, dict):
                        orders = result.get('orders', [])
                        
                        if not orders:
                            self.logger.info(f"No orders in batch {batch + 1}")
                            continue
                        
                        all_orders.extend(orders)
                        self.logger.info(f"Batch {batch + 1}: fetched {len(orders)} orders")
                        
                        # If we got less than 100, we've reached the end
                        if len(orders) < 100:
                            break
                        
                        offset += 100
                        time.sleep(1)  # Delay between requests
                    else:
                        self.logger.info(f"No valid result in batch {batch + 1}")
                        continue
                elif isinstance(data, dict):
                    orders = data.get('orders', [])
                    if orders:
                        all_orders.extend(orders)
                        self.logger.info(f"Batch {batch + 1}: fetched {len(orders)} orders")
                        if len(orders) < 100:
                            break
                        offset += 100
                        time.sleep(1)
                    else:
                        self.logger.info(f"No orders in batch {batch + 1}")
                        continue
                else:
                    self.logger.info(f"No valid data in batch {batch + 1}")
                    continue

            # Transform and return all collected orders
            transformed_orders = self._transform_orders(all_orders)
            self.logger.info(f"Transformed {len(transformed_orders)} orders")
            return transformed_orders

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching orders: {str(e)}")
            if len(all_orders) > 0:
                # Return partial results if we have some data
                self.logger.info(f"Returning {len(all_orders)} orders despite error")
                return self._transform_orders(all_orders)
            raise Exception(f"Failed to fetch orders from OPDV: {str(e)}")

    def get_customers(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Extract customers from OPDV orders (OPDV doesn't have separate customers endpoint)"""
        if not self._is_configured():
            raise Exception("OPDV service not configured")

        try:
            # Get orders first, then extract unique customers
            orders = self.get_orders(limit)
            customers_dict = {}

            for order in orders:
                customer_id = order.get('customer_id')
                customer_name = order.get('customer_name')

                if customer_id and customer_id not in customers_dict:
                    # Extract CPF from original order data
                    original_data = order.get('original_data', {})
                    customer_cpf = str(original_data.get('customerCpf', ''))
                    customer_email = original_data.get('customerEmail', '')
                    customer_phone = original_data.get('customerPhone', '')
                    
                    customers_dict[customer_id] = {
                        'external_id': customer_id,
                        'name': customer_name or '',
                        'email': customer_email,
                        'phone': customer_phone,
                        'document': customer_cpf,  # Extract CPF from OPDV data
                        'address': {
                            'street': original_data.get('street', ''),
                            'city': original_data.get('city', ''),
                            'state': original_data.get('state', ''),
                            'zip_code': str(original_data.get('cep', ''))
                        },
                        'created_date': order.get('created_date', ''),
                        'source': 'OPDV'
                    }

            customers_list = list(customers_dict.values())
            self.logger.info(
                f"Extracted {len(customers_list)} unique customers from orders"
            )
            return customers_list

        except Exception as e:
            self.logger.error(f"Error extracting customers: {str(e)}")
            raise Exception(f"Failed to extract customers from OPDV: {str(e)}")

    def _is_configured(self) -> bool:
        """Check if service is properly configured"""
        return bool(self.base_url and self.api_key)

    def _transform_orders(self, orders: List[Dict]) -> List[Dict[str, Any]]:
        """Transform OPDV orders to standard format for Omie integration"""
        transformed = []

        for order in orders:
            # OPDV API returns values in centavos (cents), convert to reais
            total_amount = float(order.get('total', 0)) / 100
            product_total = float(order.get('productTotal', 0)) / 100
            delivery_fee = float(order.get('deliveryFee', 0)) / 100
            discount = float(order.get('discount', 0)) / 100

            transformed_order = {
                'external_id': order.get('id'),
                'order_number': order.get('label', order.get('id')),
                'customer_id': order.get('customerId'),
                'customer_name': order.get('clientName', ''),
                'total_amount': total_amount,
                'product_total': product_total,
                'delivery_fee': delivery_fee,
                'discount': discount,
                'status': order.get('status', 'pending'),
                'order_type':
                order.get('orderType',
                          ''),  # Canal de venda (iFood, Anotaí, etc)
                'payment_type': order.get('paymentType', ''),
                'created_date': order.get('createdDate', ''),
                'competence_date': order.get('competenceDate', ''),
                'store_id': order.get('storeId'),
                'virtual_store_id': order.get('virtualStoreId'),
                'promocode': order.get('promocode', ''),
                'items': self._transform_order_items(order.get('items', [])),
                'payments': self._transform_payments(order.get('payments',
                                                               [])),
                'customer_address': {
                    'street': order.get('street', ''),
                    'city': order.get('city', ''),
                    'state': order.get('state', ''),
                    'neighborhood': order.get('neighborhood', ''),
                    'cep': order.get('cep', ''),
                    'number': order.get('number', ''),
                    'complement': order.get('complement', ''),
                    'lat': order.get('lat'),
                    'long': order.get('long')
                },
                'source': 'OPDV',
                'sales_channel': self._identify_sales_channel(order),  # Use sales_channel key
                'channel': self._identify_sales_channel(order),  # Also keep channel for compatibility
                'original_data': order  # Keep original for reference
            }
            transformed.append(transformed_order)

        return transformed

    def _transform_customers(self,
                             customers: List[Dict]) -> List[Dict[str, Any]]:
        """Transform OPDV customers to standard format"""
        transformed = []

        for customer in customers:
            transformed_customer = {
                'external_id': customer.get('id'),
                'name': customer.get('name', ''),
                'email': customer.get('email', ''),
                'phone': customer.get('phone', ''),
                'document': customer.get('document',
                                         customer.get('cpf_cnpj', '')),
                'address': {
                    'street': customer.get('address', {}).get('street', ''),
                    'city': customer.get('address', {}).get('city', ''),
                    'state': customer.get('address', {}).get('state', ''),
                    'zip_code': customer.get('address',
                                             {}).get('zip_code', '')
                },
                'created_date': customer.get('created_at', ''),
                'source': 'OPDV'
            }
            transformed.append(transformed_customer)

        return transformed

    def _transform_order_items(self,
                               items: List[Dict]) -> List[Dict[str, Any]]:
        """Transform order items to standard format"""
        transformed = []

        for item in items:
            # OPDV API returns values in centavos (cents), convert to reais
            unit_price = float(item.get('price', 0)) / 100
            total_price = float(item.get('total', 0)) / 100

            transformed_item = {
                'product_id': item.get('productSKU', ''),
                'name': item.get('productName', ''),  # Use 'name' instead of 'product_name'
                'description': item.get('productName', ''),  # Also add description field
                'quantity': float(item.get('quantity', 1)),
                'unit_price': unit_price,
                'total_price': total_price
            }
            transformed.append(transformed_item)

        return transformed

    def _transform_payments(self, payments: List[Dict]) -> List[Dict[str, Any]]:
        """Transform OPDV payments to standard format using correct field names"""
        transformed = []
        
        # Log raw payment data for debugging
        print(f"DEBUG: Raw payments data: {payments}")
        
        # If no payments data, try to detect from order info
        if not payments:
            print(f"DEBUG: No payments data found, will use default mapping")
        
        for payment in payments:
            # OPDV API uses different field names - map to our standard format
            # paymentValue is in centavos (cents), convert to reais
            amount = float(payment.get('paymentValue', 0)) / 100
            payment_method = payment.get('paymentMethod', '')
            
            # Log individual payment for debugging
            print(f"DEBUG: Processing payment - Method: '{payment_method}', Amount: {amount}, Raw: {payment}")
            
            # Map OPDV payment method to our standard format
            method_normalized = payment_method.lower()
            
            # Detect payment type from method name
            if 'pix' in method_normalized:
                standard_method = 'pix'
            elif 'dinheiro' in method_normalized or 'cash' in method_normalized:
                standard_method = 'dinheiro'
            elif 'credito' in method_normalized or 'credit' in method_normalized:
                standard_method = 'cartao_credito'
            elif 'debito' in method_normalized or 'debit' in method_normalized:
                standard_method = 'cartao_debito'
            elif 'online' in method_normalized:
                standard_method = 'online'  # Payment via app/online
            else:
                standard_method = method_normalized
            
            transformed_payment = {
                'method': standard_method,  # Standardized method name
                'amount': amount,
                'status': 'completed' if amount > 0 else 'pending',  # Assume completed if has value
                'transaction_id': str(payment.get('paymentAuthNumber', '')),
                'original_method': payment_method,  # Keep original for reference
                'change_amount': float(payment.get('paymentChange', 0)) / 100
            }
            transformed.append(transformed_payment)
        
        self.logger.debug(f"Transformed payments: {transformed}")
        return transformed

    def _identify_sales_channel(self, order: Dict) -> str:
        """Identify sales channel from order data"""
        # OPDV returns OrderType as string with channel name
        order_type = str(order.get('orderType', '')).strip()
        
        # Log for debugging
        print(f"DEBUG: Order {order.get('id')} - OrderType: '{order_type}', SourceId: {order.get('sourceId')}")
        
        # Direct mapping from OrderType field (most reliable)
        if order_type.lower() == 'ifood':
            return 'iFood'
        elif order_type.lower() in ['anota ai', 'anotai', 'anotaí']:
            return 'Anotaí'
        elif order_type.lower() in ['uber eats', 'uber', 'ubereats']:
            return 'Uber Eats'
        elif order_type.lower() == 'rappi':
            return 'Rappi'
        
        # Fallback: Check observation field for platform indicators
        observation = str(order.get('observation', '')).lower()
        if 'ifood' in observation or 'id ifood' in observation:
            return 'iFood'
        elif 'anotai' in observation or 'anotaí' in observation:
            return 'Anotaí'
        elif 'uber' in observation or 'ubereats' in observation:
            return 'Uber Eats'
        elif 'rappi' in observation:
            return 'Rappi'
        
        # Check sourceId for additional detection
        source_id = order.get('sourceId', 0)
        if source_id == 102:  # Common iFood source ID
            return 'iFood'
        elif source_id == 103:  # Common Anotaí source ID  
            return 'Anotaí'
        elif source_id == 101:  # Common Uber Eats source ID
            return 'Uber Eats'
        
        # Check other indicators
        if 'telefone' in observation or 'phone' in observation:
            return 'Telefone'
        elif 'balcao' in observation or 'balcão' in observation or order_type == '0':
            return 'Balcão'
        elif order.get('paidOnline', 0) == 1:
            return 'Online'
        
        # If orderType has content but doesn't match known platforms, use it
        if order_type and order_type not in ['0', '1']:
            return order_type
        
        return 'Balcão'  # Default for unknown
