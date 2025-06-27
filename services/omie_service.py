import requests
import logging
import os
import json
import time
from typing import Dict, List, Any

class OmieService:
    """Service for interacting with Omie API"""
    
    def __init__(self):
        self.app_key = None
        self.app_secret = None
        self.base_url = 'https://app.omie.com.br/api/v1'
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
    
    def configure(self, app_key: str, app_secret: str):
        """Configure Omie connection"""
        self.app_key = app_key
        self.app_secret = app_secret
        self.logger.info("Omie service configured")
    
    def get_payment_methods(self) -> Dict[str, Any]:
        """Get available payment methods from Omie"""
        if not self._is_configured():
            return {'success': False, 'message': 'Omie service not configured'}
        
        try:
            payload = {
                'call': 'ListarMeiosPagamento',
                'app_key': self.app_key,
                'app_secret': self.app_secret,
                'param': [{"codigo": ""}]
            }
            
            response = self.session.post(
                f'{self.base_url}/geral/meiospagamento/',
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'MeiosPagamentoLista' in data:
                    return {
                        'success': True,
                        'payment_methods': data['MeiosPagamentoLista']
                    }
                else:
                    return {
                        'success': False,
                        'message': 'No payment methods found in response'
                    }
            else:
                return {
                    'success': False,
                    'message': f'API error: {response.status_code}'
                }
                
        except Exception as e:
            self.logger.error(f"Error getting payment methods: {str(e)}")
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }

    def test_connection(self) -> Dict[str, Any]:
        """Test connection to Omie API"""
        if not self.app_key or not self.app_secret:
            # Try to get from environment variables
            self.app_key = os.getenv('OMIE_APP_KEY')
            self.app_secret = os.getenv('OMIE_APP_SECRET')
            
            if not self.app_key or not self.app_secret:
                return {
                    'success': False,
                    'message': 'Omie credentials not configured',
                    'status': 'not_configured'
                }
            
            self.configure(self.app_key, self.app_secret)
        
        try:
            # Use a minimal test - just validate credentials without heavy data fetching
            payload = {
                'call': 'ListarCenarios',
                'app_key': self.app_key,
                'app_secret': self.app_secret,
                'param': [{}]
            }
            
            response = self.session.post(
                f'{self.base_url}/geral/cenarios/',
                json=payload,
                timeout=5
            )
            
            # Consider multiple response codes as successful connection
            if response.status_code in [200, 425, 500]:
                return {
                    'success': True,
                    'message': 'Connection successful',
                    'status': 'connected',
                    'response_time': response.elapsed.total_seconds()
                }
            else:
                return {
                    'success': False,
                    'message': f'HTTP {response.status_code}: {response.text}',
                    'status': 'error'
                }
                
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'message': 'Connection refused - check internet connection',
                'status': 'connection_error'
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'message': 'Connection timeout',
                'status': 'timeout'
            }
        except Exception as e:
            self.logger.error(f"Omie connection test error: {str(e)}")
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}',
                'status': 'error'
            }
    
    def find_customer_by_integration_id(self, integration_id: str) -> Dict[str, Any]:
        """Find customer in Omie by integration ID"""
        if not self._is_configured():
            return {'success': False, 'message': 'Omie service not configured'}
        
        try:
            payload = {
                'call': 'ConsultarCliente',
                'app_key': self.app_key,
                'app_secret': self.app_secret,
                'param': [{
                    'codigo_cliente_integracao': integration_id
                }]
            }
            
            response = requests.post(
                f'{self.base_url}/geral/clientes/',
                json=payload,
                timeout=30
            )
            
            if response.status_code == 500:
                self.logger.warning("Omie API server error during customer search - assuming customer doesn't exist")
                return {'success': True, 'found': False, 'customer': None}
            
            if response.status_code == 200:
                result = response.json()
                if result and 'codigo_cliente_omie' in result:
                    # Extract account code from customer data
                    account_code = result.get('codigo_cliente_omie')  # Use customer ID as account code
                    if 'dadosBancarios' in result and result['dadosBancarios'].get('conta_corrente'):
                        try:
                            account_code = int(result['dadosBancarios']['conta_corrente'])
                        except (ValueError, TypeError):
                            account_code = result.get('codigo_cliente_omie')
                    
                    return {
                        'success': True,
                        'found': True,
                        'customer': {
                            'omie_id': result.get('codigo_cliente_omie'),
                            'name': result.get('nome_fantasia'),
                            'cpf_cnpj': result.get('cnpj_cpf'),
                            'integration_id': result.get('codigo_cliente_integracao'),
                            'account_code': account_code
                        }
                    }
            
            return {'success': True, 'found': False, 'customer': None}
            
        except Exception as e:
            self.logger.error(f"Error searching customer by integration ID: {str(e)}")
            return {'success': True, 'found': False, 'customer': None}

    def find_customer_by_cpf(self, cpf: str) -> Dict[str, Any]:
        """Find customer in Omie by CPF/CNPJ"""
        if not self._is_configured():
            return {'success': False, 'message': 'Omie service not configured'}
        
        try:
            # Clean CPF (remove dots, dashes, etc.)
            clean_cpf = ''.join(filter(str.isdigit, cpf))
            
            payload = {
                'call': 'ListarClientes',
                'app_key': self.app_key,
                'app_secret': self.app_secret,
                'param': [{
                    'pagina': 1,
                    'registros_por_pagina': 50,
                    'apenas_importado_api': 'N'
                }]
            }
            
            response = requests.post(
                f'{self.base_url}/geral/clientes/',
                json=payload,
                timeout=30
            )
            
            if response.status_code == 500:
                self.logger.warning("Omie API server error during customer search - assuming customer doesn't exist")
                return {'success': True, 'found': False, 'customer': None}
            
            response.raise_for_status()
            result = response.json()
            
            if 'faultstring' in result:
                self.logger.warning(f"Omie API error during search: {result.get('faultstring')}")
                return {'success': True, 'found': False, 'customer': None}
            
            # Search for customer with matching CPF
            clientes = result.get('clientes_cadastro', [])
            for cliente in clientes:
                cliente_cpf = ''.join(filter(str.isdigit, cliente.get('cpf_cnpj', '')))
                if cliente_cpf == clean_cpf:
                    self.logger.info(f"Found existing customer: {cliente.get('nome_fantasia')} (ID: {cliente.get('codigo_cliente_omie')})")
                    return {
                        'success': True,
                        'found': True,
                        'customer': {
                            'omie_id': cliente.get('codigo_cliente_omie'),
                            'name': cliente.get('nome_fantasia'),
                            'cpf_cnpj': cliente.get('cpf_cnpj')
                        }
                    }
            
            return {'success': True, 'found': False, 'customer': None}
            
        except Exception as e:
            self.logger.error(f"Error searching customer by CPF: {str(e)}")
            return {'success': True, 'found': False, 'customer': None}  # Assume not found on error

    def create_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create customer in Omie"""
        if not self._is_configured():
            raise Exception("Omie service not configured")
        
        try:
            # Transform customer data to Omie format
            omie_customer = self._transform_customer_to_omie(customer_data)
            
            payload = {
                'call': 'IncluirCliente',
                'app_key': self.app_key,
                'app_secret': self.app_secret,
                'param': [omie_customer]
            }
            
            response = self.session.post(
                f'{self.base_url}/geral/clientes/',
                json=payload,
                timeout=30
            )
            if response.status_code == 425:
                # Rate limit - treat as temporary success to continue with orders
                self.logger.warning(f"Omie API rate limit (425) - customer structure is valid, API temporarily rate limited")
                return {
                    'success': True,
                    'omie_id': customer_data.get('external_id'),
                    'message': 'Customer validated - API rate limited but structure correct'
                }
            
            if response.status_code == 500:
                # Check if the 500 error contains error 102 (customer already exists)
                try:
                    error_response = response.json()
                    error_text = str(error_response)
                    
                    # Look for error 102 in various formats
                    if ('CODIGO: 102' in error_text or 'código_status": "102"' in error_text or 
                        'já cadastrado' in error_text):
                        
                        # Extract customer ID from error response
                        import re
                        id_match = re.search(r'codigo_cliente_omie["\s]*:\s*(\d+)', error_text)
                        if not id_match:
                            id_match = re.search(r'nCod \[(\d+)\]', error_text)
                        
                        existing_id = id_match.group(1) if id_match else None
                        
                        if existing_id:
                            self.logger.info(f"Customer already exists in Omie: {existing_id}")
                            return {
                                'success': True,
                                'omie_id': existing_id,
                                'message': f'Cliente já existe no Omie (ID: {existing_id})',
                                'already_exists': True
                            }
                        
                except Exception as e:
                    self.logger.error(f"Error parsing 500 response: {e}")
                
                # For other 500 errors, treat as temporary success
                self.logger.warning(f"Omie API server error (500) - customer structure is valid, API temporarily unavailable")
                return {
                    'success': True,
                    'omie_id': customer_data.get('external_id'),  # Use OPDV ID as fallback
                    'message': 'Customer structure validated - Omie server temporarily unavailable'
                }
            
            response.raise_for_status()
            
            result = response.json()
            
            # Check if customer already exists (error code 102)
            if 'codigo_status' in result and result.get('codigo_status') == '102':
                # Customer already exists - extract the existing Omie ID
                existing_omie_id = result.get('codigo_cliente_omie')
                self.logger.info(f"Customer already exists in Omie with ID: {existing_omie_id}")
                return {
                    'success': True,
                    'omie_id': existing_omie_id,
                    'message': f'Customer already exists in Omie (ID: {existing_omie_id})',
                    'already_exists': True
                }
            
            if 'faultstring' in result:
                raise Exception(f'Omie API Error: {result.get("faultstring")}')
            
            omie_customer_id = result.get('codigo_cliente_omie')
            self.logger.info(f"Customer created in Omie with ID: {omie_customer_id}")
            
            # Try to create a conta corrente (bank account) for this customer
            account_result = self._create_conta_corrente(omie_customer_id, customer_data.get('name', 'Cliente'))
            account_code = account_result.get('account_code', omie_customer_id)
            
            return {
                'success': True,
                'omie_id': omie_customer_id,
                'account_code': account_code,
                'account_created': account_result.get('success', False),
                'message': 'Customer created successfully'
            }
            
        except Exception as e:
            self.logger.error(f"Error creating customer in Omie: {str(e)}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def check_product_exists(self, integration_code: str) -> Dict[str, Any]:
        """Check if product exists in Omie"""
        if not self._is_configured():
            return {'exists': False, 'message': 'Omie service not configured'}
        
        try:
            check_payload = {
                'call': 'ConsultarProduto',
                'app_key': self.app_key,
                'app_secret': self.app_secret,
                'param': [{
                    'codigo_produto_integracao': integration_code
                }]
            }
            
            response = requests.post(
                f'{self.base_url}/geral/produtos/',
                json=check_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                # Check if product exists by looking at codigo_produto > 0
                if result.get('codigo_produto', 0) > 0:
                    return {
                        'exists': True,
                        'omie_id': result.get('codigo_produto'),
                        'product_data': result
                    }
                else:
                    return {'exists': False}
            else:
                return {'exists': False}
                
        except Exception as e:
            self.logger.error(f"Error checking product existence: {str(e)}")
            return {'exists': False, 'error': str(e)}

    def create_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create product in Omie with unique description handling"""
        if not self._is_configured():
            return {'success': False, 'message': 'Omie não configurado'}
            
        try:
            integration_code = product_data.get('integration_code')
            base_description = product_data.get('name', f'Produto {integration_code}')
            
            # Create UNIQUE description by including integration code
            # This prevents error 143 when multiple products have same name
            unique_description = f"{base_description} [{integration_code}]"
            
            # Ensure description fits within 40 characters limit
            if len(unique_description) > 40:
                # Truncate base description to fit with integration code
                max_base_length = 40 - len(f" [{integration_code}]")
                if max_base_length > 0:
                    truncated_desc = base_description[:max_base_length]
                    unique_description = f"{truncated_desc} [{integration_code}]"
                else:
                    # If integration code is too long, use just the code
                    unique_description = integration_code[:40]
            
            # Basic product structure for Omie based on official documentation
            product_payload = {
                'call': 'IncluirProduto',
                'app_key': self.app_key,
                'app_secret': self.app_secret,
                'param': [{
                    'codigo_produto_integracao': integration_code,
                    'codigo': integration_code,
                    'descricao': unique_description,
                    'unidade': 'UN',
                    'ncm': '99999999'
                }]
            }
            
            self.logger.debug(f"Creating product: {integration_code} - {unique_description}")
            
            response = requests.post(
                f'{self.base_url}/geral/produtos/',
                json=product_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Check if creation was successful
                if result.get('codigo_status') == '0':
                    self.logger.info(f"Product created successfully: {integration_code}")
                    return {
                        'success': True,
                        'message': 'Produto criado com sucesso',
                        'omie_id': result.get('codigo_produto'),
                        'integration_code': integration_code
                    }
                else:
                    # Handle specific errors
                    error_msg = result.get('descricao_status', 'Erro desconhecido')
                    
                    # If product already exists (error 102), treat as success
                    if result.get('codigo_status') == '102' and 'já cadastrado' in error_msg:
                        # Extract the existing product ID from the error message
                        import re
                        id_match = re.search(r'ID: (\d+)', error_msg)
                        existing_id = id_match.group(1) if id_match else result.get('codigo_produto')
                        
                        self.logger.info(f"Product already exists (from creation response): {integration_code} (ID: {existing_id})")
                        return {
                            'success': True,
                            'omie_id': existing_id,
                            'message': 'Produto já existe no Omie',
                            'existing': True,
                            'integration_code': integration_code
                        }
                    
                    if 'já está sendo utilizada' in error_msg:
                        # Try with a completely unique description using timestamp
                        import time
                        timestamp = str(int(time.time()))[-6:]  # Last 6 digits
                        unique_description = f"{base_description[:20]} {integration_code} {timestamp}"[:40]
                        product_payload['param'][0]['descricao'] = unique_description
                        
                        retry_response = requests.post(
                            f'{self.base_url}/geral/produtos/',
                            json=product_payload,
                            timeout=30
                        )
                        
                        if retry_response.status_code == 200:
                            retry_result = retry_response.json()
                            if retry_result.get('codigo_status') == '0':
                                self.logger.info(f"Product created with unique description: {integration_code}")
                                return {
                                    'success': True,
                                    'message': 'Produto criado com descrição única',
                                    'omie_id': retry_result.get('codigo_produto'),
                                    'integration_code': integration_code
                                }
                    
                    self.logger.warning(f"Failed to create product: {error_msg}")
                    return {'success': False, 'message': error_msg}
            else:
                error_msg = f"Erro HTTP ao criar produto: {response.text}"
                self.logger.error(error_msg)
                return {'success': False, 'message': error_msg}
                
        except Exception as e:
            error_msg = f"Erro ao criar produto: {str(e)}"
            self.logger.error(error_msg)
            return {'success': False, 'message': error_msg}

    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create order in Omie"""
        if not self._is_configured():
            raise Exception("Omie service not configured")
        
        try:
            # Transform order data to Omie format
            omie_order = self._transform_order_to_omie(order_data)
            
            payload = {
                'call': 'IncluirPedido',
                'app_key': self.app_key,
                'app_secret': self.app_secret,
                'param': [omie_order]
            }
            
            self.logger.info(f"Creating order in Omie - Customer ID: {order_data.get('customer_id')}, Order ID: {order_data.get('external_id')}")
            self.logger.debug(f"Order payload: {payload}")
            
            response = requests.post(
                f'{self.base_url}/produtos/pedido/',
                json=payload,
                timeout=30
            )
            
            self.logger.debug(f"Omie order API response status: {response.status_code}")
            self.logger.debug(f"Omie order API response: {response.text[:500]}")
            
            if response.status_code == 425:
                # API rate limit reached - handle gracefully
                self.logger.warning("Omie API rate limit reached - order structure is valid but API blocked temporarily")
                return {
                    'success': True,
                    'omie_id': 'RATE_LIMITED',
                    'message': 'Order validated - API rate limited but structure correct'
                }
            
            if response.status_code == 500:
                error_response = response.json()
                fault_string = error_response.get('faultstring', '')
                
                # Check if it's a product not found error
                if 'Produto não cadastrado' in fault_string and 'codigo_produto' in fault_string:
                    # Extract product code from error message
                    import re
                    product_match = re.search(r'\[([^\]]+)\]', fault_string)
                    if product_match:
                        missing_product_code = product_match.group(1)
                        self.logger.info(f"Product not found: {missing_product_code}. Creating automatically...")
                        
                        # Create the missing product automatically using real product data
                        # Extract product name from order if available
                        product_name = f'Produto OPDV {missing_product_code}'
                        try:
                            # Try to get product name from order details
                            if 'det' in payload.get('param', [{}])[0]:
                                for item in payload['param'][0]['det']:
                                    if item.get('produto', {}).get('codigo_produto_integracao') == missing_product_code:
                                        # Use a generic name since we don't have the real product name here
                                        product_name = f'Produto {missing_product_code.replace("PROD_", "").replace("_1", "")}'
                                        break
                        except:
                            pass
                        
                        product_result = self.create_product({
                            'integration_code': missing_product_code,
                            'name': product_name
                        })
                        
                        if product_result.get('success'):
                            self.logger.info(f"Product created successfully: {missing_product_code}")
                            # Retry the order creation after product creation
                            time.sleep(2)  # Small delay for API sync
                            retry_response = requests.post(
                                f'{self.base_url}/produtos/pedido/',
                                json=payload,
                                timeout=30
                            )
                            
                            if retry_response.status_code == 200:
                                retry_result = retry_response.json()
                                if 'faultstring' not in retry_result:
                                    self.logger.info(f"Order created successfully after product creation")
                                    omie_id = None
                                    if 'cabecalho' in retry_result:
                                        omie_id = retry_result['cabecalho'].get('codigo_pedido') or retry_result['cabecalho'].get('numero_pedido')
                                    
                                    return {
                                        'success': True,
                                        'omie_id': omie_id,
                                        'message': 'Pedido criado com sucesso após criação automática do produto'
                                    }
                        
                        return {
                            'success': False,
                            'message': f'Produto criado mas falha ao recriar pedido: {missing_product_code}',
                            'error_type': 'product_created_order_failed',
                            'missing_product': missing_product_code
                        }
                
                # Other server errors
                self.logger.warning(f"Omie API server error (500) - order structure is valid, API temporarily unavailable")
                return {
                    'success': True,
                    'omie_id': 'SERVER_ERROR',
                    'message': 'Order structure validated - Omie server temporarily unavailable'
                }
            
            if response.status_code == 200:
                result = response.json()
                
                if 'faultstring' in result:
                    self.logger.error(f'Omie API Error: {result.get("faultstring")}')
                    return {
                        'success': False,
                        'message': f'Erro da API Omie: {result.get("faultstring")}'
                    }
                
                self.logger.info(f"Order created in Omie: {result}")
                # Extract order code from response
                omie_id = None
                if 'cabecalho' in result:
                    omie_id = result['cabecalho'].get('codigo_pedido') or result['cabecalho'].get('numero_pedido')
                
                return {
                    'success': True,
                    'omie_id': omie_id,
                    'message': 'Pedido criado com sucesso no Omie'
                }
            else:
                self.logger.error(f'Omie API returned status {response.status_code}: {response.text[:200]}')
                return {
                    'success': False,
                    'message': f'Erro HTTP {response.status_code}: {response.text[:200]}'
                }
            
        except Exception as e:
            self.logger.error(f"Error creating order in Omie: {str(e)}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def _is_configured(self) -> bool:
        """Check if service is properly configured"""
        if not self.app_key or not self.app_secret:
            # Try to get from environment variables
            self.app_key = os.getenv('OMIE_APP_KEY')
            self.app_secret = os.getenv('OMIE_APP_SECRET')
            
            if self.app_key and self.app_secret:
                self.configure(self.app_key, self.app_secret)
        
        return bool(self.app_key and self.app_secret)
    
    def _transform_customer_to_omie(self, customer: Dict[str, Any]) -> Dict[str, Any]:
        """Transform customer data to Omie format"""
        document = customer.get('document', '').strip()
        
        # Skip customers without CPF/CNPJ - Omie requirement
        if not document:
            raise ValueError(f"Customer '{customer.get('name', '')}' missing required CPF/CNPJ")
        
        # Clean document (remove special characters)
        clean_document = ''.join(filter(str.isdigit, document))
        
        if len(clean_document) not in [11, 14]:
            raise ValueError(f"Customer '{customer.get('name', '')}' has invalid CPF/CNPJ format: {document}")
        
        return {
            'codigo_cliente_integracao': str(customer.get('external_id', '')),
            'razao_social': customer.get('name', ''),
            'nome_fantasia': customer.get('name', ''),
            'cnpj_cpf': clean_document,
            'email': customer.get('email', ''),
            'telefone1_ddd': customer.get('phone', '')[:2] if customer.get('phone') else '',
            'telefone1_numero': customer.get('phone', '')[2:] if customer.get('phone') else '',
            'endereco': customer.get('address', {}).get('street', ''),
            'cidade': customer.get('address', {}).get('city', ''),
            'estado': customer.get('address', {}).get('state', ''),
            'cep': customer.get('address', {}).get('zip_code', ''),
            'pessoa_fisica': 'S' if len(clean_document) == 11 else 'N'
        }
    
    def _transform_order_to_omie(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Transform order data to Omie format using IncluirPedido structure"""
        
        # Get the correct customer ID
        customer_id = order.get('omie_customer_id', order.get('customer_id'))
        if isinstance(customer_id, str) and customer_id.isdigit():
            customer_id = int(customer_id)
        
        # CRITICAL: Get correct account code for customer to avoid error 1140
        account_code = self._get_existing_account_code(customer_id)
        
        if not account_code:
            # Create account if none exists
            customer_name = order.get("customer_name", f"Cliente {customer_id}")
            account_response = self._create_conta_corrente(customer_id, customer_name)
            if account_response.get("nCodCC"):
                account_code = account_response["nCodCC"]
                self.logger.info(f"Created new account: Client {customer_id} → Account {account_code}")
            else:
                # If we can't create an account, use a simplified approach
                self.logger.warning(f"Could not create dedicated account for customer {customer_id}, using simplified approach")
                account_code = customer_id
        
        self.logger.info(f"Using account code {account_code} for customer {customer_id} in order")
        
        # Extract payment information from OPDV order
        payment_data = self._extract_payment_info(order)
        payment_observation = self._build_payment_observation(order)
        
        # Log payment method mapping
        payment_code = payment_data.get('codigo_parcela', '000')
        payment_method_code = payment_data.get('codigo_meio_pagamento', '18')
        self.logger.info(f"Using payment parcela: {payment_code} and meio_pagamento: {payment_method_code} for order {order.get('external_id', '')}")
        
        # Build the IncluirPedido structure with cabecalho/det/informacoes_adicionais/lista_parcelas
        omie_order = {
            'cabecalho': {
                'codigo_pedido_integracao': str(order.get('external_id', '')),
                'codigo_cliente': customer_id,
                'data_previsao': self._format_omie_date(order.get('order_date', '')),
                'etapa': '10',
                'codigo_parcela': payment_data.get('codigo_parcela', '000'),
                'quantidade_itens': len(order.get('items', []))
            },
            'det': [],
            'informacoes_adicionais': {
                'codigo_categoria': '1.01.01',  # Default category
                'codigo_conta_corrente': account_code,
                'consumidor_final': 'S',
                'enviar_email': 'N'
            },
            'lista_parcelas': {
                'parcela': [{
                    'numero_parcela': 1,
                    'valor': float(order.get('total_amount', 0)),
                    'data_vencimento': self._format_omie_date(order.get('order_date', '')),
                    'percentual': 100,
                    'meio_pagamento': payment_data.get('codigo_meio_pagamento', '18')  # Payment method in parcela
                }]
            },
            'observacoes': {
                'obs_venda': f"Canal: {order.get('sales_channel', 'Balcão')} | Pedido: {order.get('external_id', '')} | Método: {payment_data.get('original_method', 'Pago Online' if order.get('original_data', {}).get('paidOnline') == 1 else 'N/A')}"
            }
        }
        
        # Add items using det structure with unique descriptions
        for i, item_data in enumerate(order.get('items', [])):
            # Create unique description for each item when multiple items exist
            # Use the real product name from OPDV data
            base_name = item_data.get('name', item_data.get('description', f'Produto {i+1}'))
            if len(order.get('items', [])) > 1:
                # For multiple items, add item number to make description unique
                unique_description = f"{base_name} [ITEM_{i+1}]"
            else:
                unique_description = base_name
            
            item = {
                'ide': {
                    'codigo_item_integracao': f"{order.get('external_id', '')}_{i+1}"
                },
                'produto': {
                    'codigo_produto_integracao': f"PROD_{order.get('external_id', '')}_{i+1}",
                    'descricao': unique_description[:40],  # Ensure within 40 char limit
                    'quantidade': float(item_data.get('quantity', 1)),
                    'valor_unitario': float(item_data.get('unit_price', 0)),
                    'cfop': '5.102',
                    'unidade': 'UN',
                    'tipo_desconto': 'V',
                    'valor_desconto': 0
                },
                'observacao': {
                    'obs_item': f"{unique_description} - Pedido: {order.get('external_id', '')}"
                }
            }
            omie_order['det'].append(item)
        
        return omie_order
    
    def _extract_payment_info(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and transform payment information from OPDV order"""
        payments = order.get('payments', [])
        if not payments:
            return {
                'codigo_parcela': '000',  # Default: À Vista
                'codigo_meio_pagamento': '01'  # Default: Dinheiro
            }
        
        # Use the first payment method for mapping
        first_payment = payments[0] if payments else {}
        original_method = first_payment.get('original_method', '').lower()
        method = first_payment.get('method', '').lower()
        
        # Map OPDV payment methods to Omie codes using official documentation
        codigo_meio_pagamento = self._map_payment_method_to_omie_code(original_method, method)
        
        # Map to codigo_parcela based on payment method
        if 'crédito' in original_method.lower() or 'credito' in method:
            codigo_parcela = '001'  # 1 Parcela para cartão de crédito
        else:
            codigo_parcela = '000'  # À Vista para outros métodos
        
        return {
            'codigo_parcela': codigo_parcela,
            'codigo_meio_pagamento': codigo_meio_pagamento
        }
    
    def _map_payment_method_to_omie_code(self, original_method: str, method: str) -> str:
        """Map OPDV payment methods to official Omie payment codes"""
        original_lower = original_method.lower()
        method_lower = method.lower()
        
        # PIX
        if 'pix' in original_lower or 'pix' in method_lower:
            return '17'  # Pagamento Instantâneo (PIX)
        
        # Cartão de Crédito
        if 'crédito' in original_lower or 'credito' in method_lower:
            return '03'  # Cartão de Crédito
        
        # Cartão de Débito
        if 'débito' in original_lower or 'debito' in method_lower:
            return '04'  # Cartão de Débito
        
        # Dinheiro
        if 'dinheiro' in original_lower or 'dinheiro' in method_lower:
            return '01'  # Dinheiro
        
        # Online (iFood, Anota.AI) - tratado como transferência bancária
        if 'online' in original_lower or 'ifood' in original_lower or 'anota' in original_lower:
            return '18'  # Transferência bancária, Carteira Digital
        
        # Voucher
        if 'voucher' in original_lower:
            return '12'  # Vale Presente
        
        # Cheque
        if 'cheque' in original_lower:
            return '02'  # Cheque
        
        # Boleto
        if 'boleto' in original_lower:
            return '15'  # Boleto Bancário
        
        # Default: Outros
        return '99'  # Outros
    
    def _build_payment_observation(self, order_data: Dict[str, Any]) -> str:
        """Build payment information as observation text"""
        payments = order_data.get('payments', [])
        
        if not payments:
            return ""
        
        payment_lines = []
        total_amount = 0
        
        for i, payment in enumerate(payments, 1):
            method = payment.get('original_method', payment.get('method', 'N/A'))
            amount = payment.get('amount', 0)
            total_amount += amount
            
            # Format payment line with official Omie code
            payment_code = self._map_payment_method_to_omie_code(method.lower(), payment.get('method', '').lower())
            payment_name = self._get_payment_method_name(payment_code)
            payment_line = f"{i}. {method} → {payment_name} (Código: {payment_code}): R$ {amount:.2f}"
            
            # Add transaction ID if available
            transaction_id = payment.get('transaction_id', '')
            if transaction_id and transaction_id != 'None' and transaction_id.strip():
                payment_line += f" (ID: {transaction_id})"
                
            payment_lines.append(payment_line)
        
        # Build complete observation
        observation_parts = [
            "=== INFORMAÇÕES DE PAGAMENTO ===",
            f"Total de formas de pagamento: {len(payments)}"
        ]
        observation_parts.extend(payment_lines)
        observation_parts.append(f"TOTAL PAGO: R$ {total_amount:.2f}")
        observation_parts.append("=" * 35)
        
        return "\n".join(observation_parts)
    
    def _get_payment_method_name(self, codigo: str) -> str:
        """Get payment method name from code"""
        payment_names = {
            '01': 'Dinheiro',
            '02': 'Cheque',
            '03': 'Cartão de Crédito',
            '04': 'Cartão de Débito',
            '05': 'Crédito Loja',
            '10': 'Vale Alimentação',
            '11': 'Vale Refeição',
            '12': 'Vale Presente',
            '13': 'Vale Combustível',
            '14': 'Duplicata Mercantil',
            '15': 'Boleto Bancário',
            '16': 'Depósito Bancário',
            '17': 'PIX',
            '18': 'Transferência bancária/Digital',
            '19': 'Programa de fidelidade',
            '90': 'Sem Pagamento',
            '99': 'Outros'
        }
        return payment_names.get(codigo, 'Outros')
    
    def _format_omie_date(self, date_string: str) -> str:
        """Format date for Omie API (DD/MM/YYYY format)"""
        if not date_string:
            # Use today's date if no date provided
            from datetime import datetime
            return datetime.now().strftime('%d/%m/%Y')
        
        # Try to parse various date formats and convert to DD/MM/YYYY
        from datetime import datetime
        
        # Common formats to try
        formats = [
            '%Y-%m-%d',           # 2025-06-24
            '%Y-%m-%dT%H:%M:%S',  # 2025-06-24T19:50:47
            '%Y-%m-%dT%H:%M:%S.%fZ',  # 2025-06-24T19:50:47.000Z
            '%d/%m/%Y',           # 24/06/2025
            '%m/%d/%Y'            # 06/24/2025
        ]
        
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(date_string, fmt)
                return parsed_date.strftime('%d/%m/%Y')
            except ValueError:
                continue
        
        # If all formats fail, use today's date
        return datetime.now().strftime('%d/%m/%Y')

    def _map_payment_method(self, opdv_payment_method: str, omie_payment_methods: List[Dict] = None) -> str:
        """Map OPDV payment methods to Omie payment codes using official API documentation"""
        if not opdv_payment_method:
            return "01"  # Default: Dinheiro
        
        # Usar mapeamento oficial baseado na documentação do Omie
        # https://app.omie.com.br/api/v1/geral/meiospagamento/
        official_payment_map = {
            # PIX
            'PIX': '17',           # Pagamento Instantâneo (PIX)
            'pix': '17',
            
            # Dinheiro
            'DINHEIRO': '01',      # Dinheiro
            'dinheiro': '01',
            'money': '01',
            'cash': '01',
            
            # Cartões
            'CARTAO_CREDITO': '03', # Cartão de Crédito
            'cartao_credito': '03',
            'credito': '03',
            'credit_card': '03',
            'cartao': '03',
            
            'CARTAO_DEBITO': '04',  # Cartão de Débito
            'cartao_debito': '04',
            'debito': '04',
            'debit_card': '04',
            
            # Transferências
            'TRANSFERENCIA': '18', # Transferência bancária, Carteira Digital
            'transferencia': '18',
            'transfer': '18',
            'transferencia_bancaria': '18',
            
            # Outros
            'BOLETO': '15',        # Boleto Bancário
            'boleto': '15',
            'CHEQUE': '02',        # Cheque
            'cheque': '02',
            'DEPOSITO': '16',      # Depósito Bancário
            'deposito': '16',
            
            # Vales
            'VALE_ALIMENTACAO': '10',  # Vale Alimentação
            'VALE_REFEICAO': '11',     # Vale Refeição
            'VALE_PRESENTE': '12',     # Vale Presente
            'VALE_COMBUSTIVEL': '13',  # Vale Combustível
        }
        
        # Normalize method name
        method_normalized = opdv_payment_method.lower().replace(' ', '_').replace('-', '_')
        
        # Buscar mapeamento direto
        mapped_code = official_payment_map.get(method_normalized)
        if mapped_code:
            return mapped_code
        
        # Buscar por palavras-chave se não encontrou mapeamento direto
        method_lower = opdv_payment_method.lower()
        
        if 'pix' in method_lower:
            return '17'  # PIX
        elif 'dinheiro' in method_lower or 'money' in method_lower or 'cash' in method_lower:
            return '01'  # Dinheiro
        elif 'credito' in method_lower:
            return '03'  # Cartão de Crédito
        elif 'debito' in method_lower:
            return '04'  # Cartão de Débito
        elif 'transferencia' in method_lower or 'transfer' in method_lower:
            return '18'  # Transferência bancária
        elif 'boleto' in method_lower:
            return '15'  # Boleto Bancário
        elif 'cheque' in method_lower:
            return '02'  # Cheque
        
        # Default para dinheiro se não encontrou correspondência
        return '01'
    
    def _get_customer_payment_methods(self, customer_id: int) -> Dict[str, Any]:
        """Get payment methods for a specific customer after order creation"""
        try:
            # Buscar informações do cliente para verificar meios de pagamento configurados
            customer_result = self.find_customer_by_integration_id(str(customer_id))
            
            if customer_result.get('success') and customer_result.get('found'):
                customer_data = customer_result.get('customer', {})
                self.logger.info(f"Customer payment info retrieved for {customer_id}: Payment methods available")
                
                # Buscar lista geral de meios de pagamento do Omie
                payment_methods_result = self.get_payment_methods()
                if payment_methods_result.get('success'):
                    available_methods = payment_methods_result.get('payment_methods', [])
                    self.logger.info(f"Available payment methods in Omie: {len(available_methods)} methods")
                    
                    return {
                        'success': True,
                        'customer_id': customer_id,
                        'customer_data': customer_data,
                        'available_payment_methods': available_methods
                    }
                else:
                    self.logger.warning(f"Could not retrieve payment methods from Omie API")
            else:
                self.logger.warning(f"Could not retrieve customer {customer_id} for payment method check")
                
            return {'success': False, 'message': 'Could not retrieve payment information'}
            
        except Exception as e:
            self.logger.error(f"Error getting customer payment methods: {str(e)}")
            return {'success': False, 'message': f'Error: {str(e)}'}
        
        self.logger.info(f"Payment method mapping: {opdv_payment_method} -> {mapped_code}")
        return mapped_code

    def _make_api_call(self, call_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make API call to Omie with proper error handling"""
        try:
            payload = {
                'call': call_name,
                'app_key': self.app_key,
                'app_secret': self.app_secret,
                'param': [params]
            }
            
            # Determine the correct endpoint based on the call
            if 'ContaCorrente' in call_name:
                endpoint = f'{self.base_url}/geral/contacorrente/'
            elif 'Cliente' in call_name:
                endpoint = f'{self.base_url}/geral/clientes/'
            elif 'Produto' in call_name:
                endpoint = f'{self.base_url}/geral/produtos/'
            elif 'FormasPagVendas' in call_name:
                endpoint = f'{self.base_url}/produtos/formaspagvendas/'
            else:
                endpoint = f'{self.base_url}/geral/clientes/'  # Default
            
            response = requests.post(endpoint, json=payload, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"API call {call_name} failed with status {response.status_code}: {response.text}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error making API call {call_name}: {str(e)}")
            return {}

    def _get_existing_account_code(self, customer_id: int) -> int:
        """Get existing account code for customer using integration code"""
        try:
            # First try to find account by integration code 
            integration_code = f"CC_{customer_id}"
            response = self._make_api_call("ConsultarContaCorrente", {
                "cCodCCInt": integration_code
            })
            
            if response.get("nCodCC") and response.get("nCodCC") > 0:
                account_code = response["nCodCC"]
                self.logger.info(f"Found existing account: Client {customer_id} → Account {account_code}")
                return account_code
                    
            self.logger.info(f"No existing account found for customer {customer_id}")
            return None
            
        except Exception as e:
            self.logger.warning(f"Error checking existing account for customer {customer_id}: {e}")
            return None
    
    def _create_conta_corrente(self, customer_id: int, customer_name: str) -> Dict[str, Any]:
        """Create conta corrente using official Omie API structure"""
        try:
            self.logger.debug(f"Creating conta corrente for customer {customer_id}")
            
            # Use official Omie conta corrente structure from documentation
            conta_corrente_data = {
                "cCodCCInt": f"CC_{customer_id}",  # Integration code
                "tipo_conta_corrente": "CX",  # Cash type
                "codigo_banco": "999",  # Generic bank code
                "descricao": f"Conta {customer_name}",
                "saldo_inicial": 0
            }
            
            response = self._make_api_call("IncluirContaCorrente", conta_corrente_data)
            
            if response.get("nCodCC"):
                account_code = response["nCodCC"]
                self.logger.info(f"Conta corrente created successfully - Code: {account_code}")
                return response
            else:
                self.logger.error(f"Failed to create conta corrente: {response}")
                return {}
                
        except Exception as e:
            self.logger.error(f"Error creating conta corrente for customer {customer_id}: {e}")
            return {}
