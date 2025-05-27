import threading
import time
import socket
import sys
import os
from src.domain.target_address import TargetAddress 
from src.domain.utils import get_current_millis, calculate_delay

class AbstractProxy(threading.Thread):
    """
    Classe base para todos os componentes do sistema distribuído (Source, LoadBalancerProxy, ServiceProxy).
    Implementa a comunicação via sockets TCP/IP para permitir que os componentes
    se comuniquem entre processos distintos.
    """
    
    def __init__(self, proxy_name: str, local_port: int, target_address: TargetAddress = None):
        super().__init__()
        self.proxy_name = proxy_name
        self.local_port = local_port
        self.target_address = target_address
        
        self.local_socket = None 
        
        
        self._outbound_connections: dict[tuple[str, int], socket.socket] = {}
        self._outbound_connections_lock = threading.Lock() 

        self.is_running = True
        self.log_writer = None
        self._log_writer_closed = False 

        self.init_log_file()
        self.start_listening() 

    def init_log_file(self):
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_file_path = os.path.join(log_dir, f"{self.proxy_name}_{self.local_port}.log")
        self.log_writer = open(log_file_path, "a", encoding='utf-8')
        self.log(f"Log iniciado para {self.proxy_name} na porta {self.local_port}")

    def log(self, message: str):
        log_entry = f"[{get_current_millis()}] {message}\n"
        print(log_entry.strip()) 

        if self.log_writer is not None:
            try:
                if not self.log_writer.closed and not self._log_writer_closed: # Verifica a nova flag
                    self.log_writer.write(log_entry)
                    self.log_writer.flush()
               
            except ValueError as e:
                sys.stderr.write(f"[{get_current_millis()}] ERROR ao escrever no arquivo de log para {self.proxy_name}: {e} - Mensagem: {message}\n")
            except Exception as e:
                sys.stderr.write(f"[{get_current_millis()}] ERRO INESPERADO durante o log para {self.proxy_name}: {e} - Mensagem: {message}\n")
        
    def start_listening(self):
        try:
            self.local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
            self.local_socket.bind(("", self.local_port))
            self.local_socket.listen(5) 
            self.log(f"[{self.proxy_name}] Escutando na porta {self.local_port}...")
            
            threading.Thread(target=self._accept_connections, daemon=True).start()
        except Exception as e:
            self.log(f"[{self.proxy_name}] ERRO ao iniciar o listener na porta {self.local_port}: {e}")
            self.is_running = False

    def _accept_connections(self):
        while self.is_running:
            try:
                conn, addr = self.local_socket.accept()
                self.log(f"[{self.proxy_name}] Conexão aceita de {addr[0]}:{addr[1]}")
                conn.settimeout(1.0) 

                threading.Thread(target=self._handle_client_connection, args=(conn, addr), daemon=True).start()
            except socket.timeout:
                continue
            except OSError as e: 
                if self.is_running:
                    self.log(f"[{self.proxy_name}] Erro OSError ao aceitar conexão: {e}")
                break 
            except Exception as e:
                if self.is_running:
                    self.log(f"[{self.proxy_name}] ERRO ao aceitar conexão: {e}")
                break


    def _handle_client_connection(self, conn: socket.socket, addr):
        buffer = ""
        self.log(f"[{self.proxy_name}] [HANDLE_CLIENT] Iniciando tratamento de conexão para {addr[0]}:{addr[1]}")
        try:
            while self.is_running:
                
                conn.settimeout(1.0) 
                data = conn.recv(4096).decode('utf-8')
                
                if not data: # Cliente fechou a conexão
                    self.log(f"[{self.proxy_name}] [HANDLE_CLIENT] Cliente {addr[0]}:{addr[1]} encerrou a conexão (recv retornou vazio).")
                    break 
                
                self.log(f"[{self.proxy_name}] [HANDLE_CLIENT] Recebido '{len(data)}' bytes de {addr[0]}:{addr[1]}. Data: '{data.strip()[:50]}'")
                buffer += data
                
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    self.log(f"[{self.proxy_name}] [HANDLE_CLIENT] Mensagem completa extraída: '{message.strip()[:50]}'")
                    self.receiving_messages(message.strip(), conn)
            
            self.log(f"[{self.proxy_name}] [HANDLE_CLIENT] Loop de recebimento encerrado para {addr[0]}:{addr[1]}.")
        except socket.timeout:
            
            self.log(f"[{self.proxy_name}] [HANDLE_CLIENT] Timeout de leitura de {addr[0]}:{addr[1]}. Conexão ociosa.")
            pass 
        except (ConnectionResetError, BrokenPipeError, socket.error) as e:
            self.log(f"[{self.proxy_name}] [HANDLE_CLIENT] Conexão com {addr[0]}:{addr[1]} foi resetada/quebrada: {e}")
            return 
        except Exception as e:
            self.log(f"[{self.proxy_name}] [HANDLE_CLIENT] ERRO inesperado na conexão do cliente {addr[0]}:{addr[1]}: {e}")
            return 
        finally:
          
            try:
                if conn:
                    
                    conn.shutdown(socket.SHUT_RDWR) 
                    conn.close()
                    self.log(f"[{self.proxy_name}] [HANDLE_CLIENT] Conexão de cliente {addr[0]}:{addr[1]} fechada.")
            except Exception as e:
                self.log(f"[{self.proxy_name}] [HANDLE_CLIENT] Erro ao fechar conexão de cliente {addr[0]}:{addr[1]}: {e}")
            self.log(f"[{self.proxy_name}] [HANDLE_CLIENT] Finalizando tratamento de conexão para {addr[0]}:{addr[1]}.")



    def _get_or_create_outbound_connection(self, target_address: TargetAddress) -> socket.socket:
        target_key = (target_address.get_ip(), target_address.get_port())

        with self._outbound_connections_lock:
            sock = self._outbound_connections.get(target_key)

            if sock and self._is_socket_connected(sock):
                self.log(f"[{self.proxy_name}] [OUTBOUND_CONN] Reutilizando conexão ativa para {target_address.get_ip()}:{target_address.get_port()}")
                return sock


            if sock:
                self.log(f"[{self.proxy_name}] [OUTBOUND_CONN] Conexão existente para {target_address.get_ip()}:{target_address.get_port()} está inativa. Fechando e removendo.")
                try:
                    sock.close()
                except Exception as e:
                    self.log(f"[{self.proxy_name}] [OUTBOUND_CONN] Erro ao fechar socket inativa para {target_key}: {e}")
                del self._outbound_connections[target_key]

            new_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                new_sock.connect(target_key)
                new_sock.settimeout(25.0) # Use um timeout maior aqui também para tentar a conexão.
                self._outbound_connections[target_key] = new_sock
                self.log(f"[{self.proxy_name}] [OUTBOUND_CONN] Conexão ESTABELECIDA com destino: {target_address.get_ip()}:{target_address.get_port()}")
                return new_sock
            except Exception as e:
                self.log(f"[{self.proxy_name}] [OUTBOUND_CONN] ERRO ao estabelecer conexão com {target_address.get_ip()}:{target_address.get_port()}: {e}")
                raise

    def _is_socket_connected(self, sock: socket.socket) -> bool:
        """
        Verifica se um socket está conectado e aparentemente funcional.
        Isso é um 'best effort', pois a conexão pode cair a qualquer momento.
        """
        try:
            
            error_code = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if error_code == 0:
                
                try:
                    sock.send(b'', socket.MSG_DONTWAIT)
                except BlockingIOError:
                    pass # Isso é esperado se não houver dados para enviar imediatamente
                return True
            else:
                self.log(f"[{self.proxy_name}] Socket {sock.fileno()} erro de SO_ERROR: {error_code}")
                return False
        except (socket.error, ConnectionResetError, BrokenPipeError):
            return False
        except Exception as e:
            self.log(f"[{self.proxy_name}] Erro inesperado ao verificar conexão do socket: {e}")
            return False

    def send_message_to_destiny(self, message: str, target_address: TargetAddress):
        """
            Envia uma mensagem para um destino específico via socket.
            Estabelece a conexão se ela ainda não existir ou estiver fechada.
        """
        try:
            sock = self._get_or_create_outbound_connection(target_address)
            sock.sendall(message.encode('utf-8'))
            self.log(f"[{self.proxy_name}] Mensagem enviada para {target_address.get_ip()}:{target_address.get_port()}: '{message.strip()}'")
        except Exception as e:
            self.log(f"[{self.proxy_name}] ERRO ao enviar mensagem para {target_address.get_ip()}:{target_address.get_port()}: {e}")
            # Em caso de erro, tenta fechar a conexão e removê-la para que uma nova seja criada na próxima tentativa
            with self._outbound_connections_lock:
                target_key = (target_address.get_ip(), target_address.get_port())
                if target_key in self._outbound_connections:
                    try:
                        self._outbound_connections[target_key].close()
                    except Exception as close_e:
                        self.log(f"[{self.proxy_name}] Erro ao fechar socket com erro para {target_key}: {close_e}")
                    del self._outbound_connections[target_key]


    
    def is_destiny_free(self, target_address: TargetAddress) -> bool:
        """
        Verifica se o destino especificado está livre para receber mensagens,
        enviando uma mensagem "ping" via socket e esperando uma resposta.
        Esta é uma transação de ping de uma única mensagem (ping-response).
        """
        try:
            
            sock = self._get_or_create_outbound_connection(target_address)
            
            data_output_stream = sock.makefile('wb')
            data_input_stream = sock.makefile('rb')

            data_output_stream.write(b"ping\n")
            data_output_stream.flush()
            
            response = data_input_stream.readline().decode('utf-8').strip() # Lê a resposta
            self.log(f"[{self.proxy_name}] Resposta de ping de {target_address.get_ip()}:{target_address.get_port()}: '{response}'")
            return response == "free"
        except socket.timeout:
            self.log(f"[{self.proxy_name}] Timeout ao verificar disponibilidade de {target_address.get_ip()}:{target_address.get_port()}. Assumindo 'busy'.")
            return False 
        except Exception as e:
            self.log(f"[{self.proxy_name}] ERRO ao verificar disponibilidade de {target_address.get_ip()}:{target_address.get_port()}: {e}")
            # Em caso de erro, remove a conexão para que uma nova seja tentada na próxima vez
            with self._outbound_connections_lock:
                target_key = (target_address.get_ip(), target_address.get_port())
                if target_key in self._outbound_connections:
                    try:
                        self._outbound_connections[target_key].close()
                    except Exception as close_e:
                        self.log(f"[{self.proxy_name}] Erro ao fechar socket com erro para {target_key}: {close_e}")
                    del self._outbound_connections[target_key]
            return False


    def stop_proxy(self):
        
        if self._log_writer_closed:
            return

        self.is_running = False
        self.log(f"[{self.proxy_name}] Sinal de parada recebido. Encerrando threads e conexões...")

        # Fecha o socket de escuta local
        if self.local_socket:
            try:
                self.local_socket.close()
                self.log(f"[{self.proxy_name}] Socket local fechado na porta {self.local_port}.")
            except Exception as e:
                self.log(f"[{self.proxy_name}] Erro ao fechar socket local: {e}")

        # Fechar todas as conexões de saída (para destinos fixos)
        with self._outbound_connections_lock:
            for target_key, sock in list(self._outbound_connections.items()):
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                    self.log(f"[{self.proxy_name}] Conexão de saída para {target_key[0]}:{target_key[1]} fechada.")
                except Exception as e:
                    self.log(f"[{self.proxy_name}] Erro ao fechar conexão de saída para {target_key[0]}:{target_key[1]}: {e}")
            self._outbound_connections.clear()
        
        # Fechar o log_writer de forma segura e apenas uma vez
        if self.log_writer is not None:
            try:
                if not self.log_writer.closed:
                    self.log_writer.close()
            except Exception as e:
                sys.stderr.write(f"[{self.proxy_name}] ERRO ao fechar log_writer: {e}\n")
            finally:
                self.log_writer = None
                self._log_writer_closed = True 

        print(f"[{get_current_millis()}] [{self.proxy_name}] Proxy completamente parado.")


    def run(self):
        self.log(f"[{self.proxy_name}] Thread principal iniciada. Aguardando mensagens...")
 
    
    def receiving_messages(self, received_message: str, conn: socket.socket):
        """
        Método abstrato para processar mensagens recebidas.
        Cada subclasse deve fornecer sua própria implementação para lidar com os dados recebidos.
        A socket 'conn' é passada para permitir que a subclasse responda na mesma conexão.
        """
        raise NotImplementedError(f"Método 'receiving_messages' deve ser implementado pela subclasse {self.__class__.__name__}.")

    def _simulate_is_free(self) -> bool:
        """
        Método abstrato para simular se o proxy (ou seu recurso principal) está livre.
        Para comunicação via socket, este método será chamado para determinar a resposta ao "ping".
        """
        raise NotImplementedError(f"Método '_simulate_is_free' deve ser implementado pela subclasse {self.__class__.__name__}.")