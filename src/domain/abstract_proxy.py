import threading
import time
import socket
import sys
import os
from src.domain.target_address import TargetAddress # Certifique-se de que TargetAddress está bem definido

class AbstractProxy(threading.Thread):
    """
    Classe base para todos os componentes do sistema distribuído (Source, LoadBalancerProxy, ServiceProxy).
    Implementa a comunicação via sockets TCP/IP para permitir que os componentes
    se comuniquem entre processos distintos.
    """
    
    def __init__(self, proxy_name: str, local_port: int, target_address: TargetAddress = None):
        """
        Construtor da classe base AbstractProxy.

        Args:
            proxy_name (str): O nome do proxy (ex: "Source", "Server1", "service2001").
            local_port (int): A porta TCP/IP na qual este proxy irá escutar por mensagens.
            target_address (TargetAddress, opcional): O endereço (IP e Porta) para onde este proxy
                                                        irá enviar suas mensagens após o processamento.
                                                        Padrão é None se não houver um destino imediato.
        """
        super().__init__()
        self.proxy_name = proxy_name
        self.local_port = local_port
        self.target_address = target_address #
        
        self.local_socket = None # Socket para escutar conexões de entrada.
        
        self._outbound_connections: dict[tuple[str, int], socket.socket] = {}
        
        self.is_running = True # Flag para controlar o ciclo de vida da thread principal.

        self.log_writer = None
        self.init_log_file()
        self.start_listening() # Inicia o servidor de socket para receber conexões.

    def init_log_file(self):
        """
        Inicializa o arquivo de log para este proxy.
        Cria um diretório 'logs' se não existir e abre um arquivo de log específico para o proxy.
        """
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_file_path = os.path.join(log_dir, f"{self.proxy_name}_{self.local_port}.log")
        self.log_writer = open(log_file_path, "a", encoding='utf-8')
        self.log(f"Log iniciado para {self.proxy_name} na porta {self.local_port}")

    def log(self, message: str):
        """
        Escreve uma mensagem no arquivo de log do proxy e no console.
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        log_entry = f"[{timestamp}] {message}\n"
        if self.log_writer:
            self.log_writer.write(log_entry)
            self.log_writer.flush()
        print(log_entry.strip())

    def start_listening(self):
        """
        Inicia o servidor de socket para este proxy, permitindo que ele receba mensagens
        de outros proxies ou componentes.
        """
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
        """
        Loop para aceitar novas conexões de entrada.
        Quando uma nova conexão é aceita, uma nova thread é iniciada para lidar com ela.
        """
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
        """
        Lida com uma conexão de cliente individual, lendo dados do socket.
        Implementa um buffer para ler mensagens delimitadas por '\n'.

        Args:
            conn (socket.socket): O objeto socket da conexão com o cliente.
            addr (tuple): O endereço (IP, Porta) do cliente conectado.
        """
        buffer = ""
        try:
            while self.is_running:
                data = conn.recv(4096).decode('utf-8')
                if not data:
                    break 
                
                buffer += data
                
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    self.receiving_messages(message.strip()) 
        except socket.timeout:
            
            pass 
        except OSError as e:
             
             self.log(f"[{self.proxy_name}] Erro na conexão com {addr[0]}:{addr[1]} (OSError): {e}")
        except Exception as e:
            self.log(f"[{self.proxy_name}] ERRO inesperado na conexão do cliente {addr[0]}:{addr[1]}: {e}")
        finally:
            self.log(f"[{self.proxy_name}] Conexão com {addr[0]}:{addr[1]} encerrada.")
            conn.close()

    def _get_or_create_outbound_connection(self, target_address: TargetAddress) -> socket.socket:
        """
        Obtém uma conexão de saída existente ou cria uma nova para o destino especificado.
        Mantém conexões persistentes no dicionário _outbound_connections.
        """
        target_key = (target_address.get_ip(), target_address.get_port())
        
        if target_key not in self._outbound_connections or not self._is_socket_connected(self._outbound_connections[target_key]):
           
            new_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                new_sock.connect(target_key)
                new_sock.settimeout(5.0) 
                self._outbound_connections[target_key] = new_sock
                self.log(f"[{self.proxy_name}] Conexão estabelecida com destino: {target_address.get_ip()}:{target_address.get_port()}")
            except Exception as e:
                self.log(f"[{self.proxy_name}] ERRO ao estabelecer conexão com {target_address.get_ip()}:{target_address.get_port()}: {e}")
                if target_key in self._outbound_connections:
                    del self._outbound_connections[target_key] 
                raise 
        return self._outbound_connections[target_key]

    def _is_socket_connected(self, sock: socket.socket) -> bool:
        """
        Verifica se um socket está conectado.
        """
        try:
            
            sock.send(b'') 
            return True
        except socket.error as e:
            return False
        except Exception as e:
            self.log(f"[{self.proxy_name}] Erro inesperado ao verificar conexão do socket: {e}")
            return False


    def send_message_to_destiny(self, message: str, target_address: TargetAddress):
        """
        Envia uma mensagem para um destino específico via socket.
        Estabelece a conexão se ela ainda não existir ou estiver fechada.

        Args:
            message (str): A mensagem a ser enviada (já deve incluir o delimitador '\n').
            target_address (TargetAddress): O endereço (IP e Porta) do destino.
        """
        try:
            sock = self._get_or_create_outbound_connection(target_address)
            sock.sendall(message.encode('utf-8'))
            self.log(f"[{self.proxy_name}] Mensagem enviada para {target_address.get_ip()}:{target_address.get_port()}: '{message.strip()}'")
        except Exception as e:
            self.log(f"[{self.proxy_name}] ERRO ao enviar mensagem para {target_address.get_ip()}:{target_address.get_port()}: {e}")
           
            target_key = (target_address.get_ip(), target_address.get_port())
            if target_key in self._outbound_connections:
                self._outbound_connections[target_key].close()
                del self._outbound_connections[target_key]


    def is_destiny_free(self, target_address: TargetAddress) -> bool:
        """
        Verifica se o destino especificado está livre para receber mensagens,
        enviando uma mensagem "ping" via socket e esperando uma resposta.

        Args:
            target_address (TargetAddress): O endereço do destino a ser verificado.

        Returns:
            bool: True se o destino estiver livre, False caso contrário.
        """
        try:
            sock = self._get_or_create_outbound_connection(target_address)
            sock.sendall(b"ping\n") 
            
           
            response = sock.recv(1024).decode('utf-8').strip() # Lê a resposta
            self.log(f"[{self.proxy_name}] Resposta de ping de {target_address.get_ip()}:{target_address.get_port()}: '{response}'")
            return response == "free"
        except socket.timeout:
            self.log(f"[{self.proxy_name}] Timeout ao verificar disponibilidade de {target_address.get_ip()}:{target_address.get_port()}. Assumindo 'busy'.")
            return False 
        except Exception as e:
            self.log(f"[{self.proxy_name}] ERRO ao verificar disponibilidade de {target_address.get_ip()}:{target_address.get_port()}: {e}")
           
            target_key = (target_address.get_ip(), target_address.get_port())
            if target_key in self._outbound_connections:
                self._outbound_connections[target_key].close()
                del self._outbound_connections[target_key]
            return False


    def stop_proxy(self):
        """
        Para a execução do proxy, fechando os sockets e liberando recursos.
        """
        self.is_running = False
        if self.local_socket:
            try:
                self.local_socket.close()
                self.log(f"[{self.proxy_name}] Socket local fechado na porta {self.local_port}.")
            except Exception as e:
                self.log(f"[{self.proxy_name}] Erro ao fechar socket local: {e}")
        

        for conn_key, sock in list(self._outbound_connections.items()): 
            try:
                sock.close()
                self.log(f"[{self.proxy_name}] Socket de destino ({conn_key[0]}:{conn_key[1]}) fechado.")
            except Exception as e:
                self.log(f"[{self.proxy_name}] Erro ao fechar socket de destino {conn_key[0]}:{conn_key[1]}: {e}")
            finally:
                del self._outbound_connections[conn_key]

        if self.log_writer:
            self.log_writer.close()
        self.log(f"[{self.proxy_name}] Proxy parado.")


    def run(self):
        """
        Método run da thread. As subclasses devem implementar sua lógica principal de processamento aqui.
        Este método base serve principalmente para iniciar o listener de socket.
        """
        self.log(f"[{self.proxy_name}] Thread principal iniciada. Aguardando mensagens...")
 

    def receiving_messages(self, received_message: str):
        """
        Método abstrato para processar mensagens recebidas.
        Cada subclasse deve fornecer sua própria implementação para lidar com os dados recebidos.
        """
        raise NotImplementedError(f"Método 'receiving_messages' deve ser implementado pela subclasse {self.__class__.__name__}.")

    def _simulate_is_free(self) -> bool:
        """
        Método abstrato para simular se o proxy (ou seu recurso principal) está livre.
        Cada subclasse deve implementar sua própria lógica para determinar se está livre.
        Para comunicação via socket, este método será chamado para determinar a resposta ao "ping".

        Returns:
            bool: True se o proxy estiver livre para processar mais trabalho, False caso contrário.
        """
        raise NotImplementedError(f"Método '_simulate_is_free' deve ser implementado pela subclasse {self.__class__.__name__}.")