import threading
import time
import socket
import sys

from src.domain.target_address import TargetAddress
from src.domain.utils import get_current_millis




class AbstractProxy(threading.Thread):
    """Classe base abstrata para todos os componentes do sistema (Source, LoadBalancerProxy, ServiceProxy).
    Ela define a interface comum e gerencia a "comunicação" interna entre os componentes na simulação in-memory.
    Os componentes podem se comunicar entre si através de mensagens, utilizando o método send_message_to_destiny.
    Essa classe também implementa um registro de proxies, permitindo que qualquer proxy envie uma mensagem para outro proxy
    simplesmente conhecendo sua porta de destino.
    A classe é responsável por gerenciar as conexões de origem e destino, além de fornecer métodos para processar mensagens.
    A classe é inicializada com o nome do proxy, a porta local e, opcionalmente, um endereço de destino.
    A classe é executada em uma thread separada, permitindo que os proxies funcionem de forma assíncrona.
    A classe também implementa um método para verificar se o proxy de destino está livre para receber mensagens.
    """
    
    
    def __init__(self, proxy_name, local_port, target_address = None):
        super().__init__()
        self.proxy_name = proxy_name
        self.local_port = local_port
        self.target_address = target_address
        self.content_to_process = None
        self.local_socket = None
        self.connection_destiny_socket = None
        self.is_running = True

        self.incoming_connections = {}
        self.outgoing_connections = {} 
        self.queue_sizes = {} 

    def run(self):
        """
            Método que inicia a execução do proxy. Ele cria um socket local e
            aguarda conexões de origem. Quando uma conexão é estabelecida, ele
            inicia uma nova thread para gerenciar essa conexão. Se um endereço de
            destino for fornecido, ele também inicia uma thread para gerenciar o
            estabelecimento de conexões de destino.
            O método também registra o proxy no dicionário de proxies para permitir
            a comunicação entre os proxies.
        """
        self._start_connection_establishment_origin_thread()
        if self.target_address:
            self._start_connection_establishment_destiny_thread()

    def _start_connection_establishment_origin_thread(self):
        """
            Inicia uma nova thread para gerenciar o estabelecimento de 
            conexões de origem
        """
        origin_thread = threading.Thread(target=self._connection_establishment_origin_task, daemon=True)
        origin_thread.start()

    def _connection_establishment_origin_task(self):
        """
            Inicia uma nova thread para gerenciar o estabelecimento de
            conexões de origem
        """
        try:
            
            pass
        except Exception as e:
            print(f"[{self.proxy_name}] Error in origin connection: {e}", file=sys.stderr)

    def _start_connection_establishment_destiny_thread(self):
        """
            Inicia uma nova thread para gerenciar o estabelecimento de
            conexões de destino
        """
        destiny_thread = threading.Thread(target=self._connection_establishment_destiny_task, daemon=True)
        destiny_thread.start()

    def _connection_establishment_destiny_task(self):
        """
            Inicia uma nova thread para gerenciar o estabelecimento de
            conexões de destino
        """
       
        self.create_connection_with_destiny()
        

    def has_something_to_process(self):
        """
            Verifica se há algo a ser processado pelo proxy

        Returns:
            bool: _description_
        """
        return self.content_to_process is not None

    def set_content_to_process(self, content_to_process):
        """
            Define o conteúdo a ser processado pelo proxy.

        Args:
            content_to_process (_type_): _description_
        """
        
        self.content_to_process = content_to_process

    def create_connection_with_destiny(self):
        """
            Cria uma conexão com o proxy de destino
        """
        
        raise NotImplementedError("Subclasses must implement create_connection_with_destiny")

    def receiving_messages(self, message: str): 
        
        print(f"[{self.proxy_name}] recebida: {message[:100]}...")

    """
        Este é um dicionário estático de classe (compartilhado por todas as instâncias de AbstractProxy e suas subclasses).
        Ele atua como um "serviço de nomes" ou "registro de componentes" na simulação.
        
        Permite que qualquer proxy envie uma mensagem para outro proxy simplesmente conhecendo sua porta de destino.
        Quando um proxy precisa enviar uma mensagem, ele busca o proxy de destino neste dicionario pela porta e invoca
        diretamente seu método receiving_messages.
        Returns:
            _type_: _description_
        """      
    _proxy_registry = {} 

    @classmethod
    def register_proxy(cls, proxy_instance):
        """ Método de classe que adiciona uma instância de proxy ao _proxy_registry
        dado uma porta local. Isso permite que proxies se comuniquem entre si.

        Args:
            proxy_instance (objeto): Instância de AbstractProxy a ser registrada.
        """
        
        cls._proxy_registry[proxy_instance.local_port] = proxy_instance

    @classmethod
    def get_proxy_by_port(cls, port):
        """
            Método de classe que busca uma instância de proxy no _proxy_registry
            a partir do numero da porta local.
        """
        return cls._proxy_registry.get(port)

    def is_destiny_free(self, target_address):
        """
            Verifica se o proxy de destino está livre para receber mensagens
            Args:
                target_address (TargetAddress): O endereço de destino a ser verificado
        """
       
        target_proxy = AbstractProxy.get_proxy_by_port(target_address.get_port())
        if target_proxy:
            return target_proxy._simulate_is_free()
        return False 

    def _simulate_is_free(self):
        """
            Simula a verificação se o proxy de destino está livre para receber mensagens.
            Esse método aqui é só um método auxiliar que é chamado pelo método is_destiny_free.
            Returns:
                bool: True se o proxy de destino estiver livre
                      False caso contrário.
        """
        return True 

    def send_message_to_destiny(self, message, target_address):
        """Envia uma mensagem para o proxy de destino, os sockets ainda não estão habilitados
        aqui para enviar mensagens, mas a comunicação entre os proxies é feita diretamente 
        através do método receiving_messages

        Args:
            message (str): mensagem a ser enviada
            target_address (TargetAddress): Endereço de destin
        """
        
        # aqui recupera o proxy de destino a partir do dicionário
        target_proxy = AbstractProxy.get_proxy_by_port(target_address.get_port())
        if target_proxy:
           # aui eu simulo um atraso só mesmo para simular um tempo de espera
            time.sleep(0.003)
            # aqui eu chamo o método receiving_messages do proxy de destino
            target_proxy.receiving_messages(message)
        else:
            print(f"[{self.proxy_name}] Could not find target proxy at port {target_address.get_port()} to send message: {message[:50]}...")