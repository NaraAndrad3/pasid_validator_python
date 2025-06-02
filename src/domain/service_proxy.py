import threading
import time
import socket
import random
import os
from src.domain.abstract_proxy import AbstractProxy
from src.domain.target_address import TargetAddress
from src.domain.utils import get_current_millis
from textblob import TextBlob


class ServiceProxy(AbstractProxy):

    def __init__(self, name: str, local_port: int, target_address: TargetAddress, service_time: float, std: float, target_is_source: bool):
        super().__init__(name, local_port, target_address)
        self.service_time = service_time
        self.std = std
        self.target_is_source = target_is_source
        self.processing_queue = []
        self.processing_lock = threading.Lock()

    def run(self):
        self.log(f"[{self.proxy_name}] Iniciando {self.proxy_name} na porta {self.local_port}...")
        while self.is_running:
            self.process_and_send_to_destiny()
            time.sleep(0.01)

    def receiving_messages(self, received_message: str, conn: socket.socket):
        if received_message is None or received_message.strip() == "":
            return

        message_stripped = received_message.strip()
        
        if message_stripped == "ping":
            self.handle_ping_message(conn)
        else:
            with self.processing_lock:
                self.processing_queue.append(self.register_time_when_arrives(message_stripped))
                self.log(f"[{self.proxy_name}] Mensagem adicionada à fila ({len(self.processing_queue)}): {message_stripped[:50]}...")

    def handle_ping_message(self, conn: socket.socket):
        try:
            output_stream = conn.makefile('wb') 
            with self.processing_lock:
                if self.processing_queue:
                    output_stream.write(b"busy\n")
                    self.log(f"[{self.proxy_name}] Respondeu 'busy' ao ping (fila com {len(self.processing_queue)} mensagens).")
                else:
                    output_stream.write(b"free\n")
                    self.log(f"[{self.proxy_name}] Respondeu 'free' ao ping.")
            output_stream.flush()
        except Exception as e:
            self.log(f"[{self.proxy_name}] ERRO ao responder ping: {e}")
            
    def _simulate_is_free(self) -> bool:
        with self.processing_lock:
            return not self.processing_queue

    def process_and_send_to_destiny(self):
        message_to_process = None
        
        with self.processing_lock:
            if not self.processing_queue:
                return
            message_to_process = self.processing_queue.pop(0)

        if message_to_process:
            delay = max(0, random.gauss(self.service_time, self.std)) / 1000.0
            time.sleep(delay)

            # 🧠 Análise de sentimento
            sentiment_result = self.analyze_sentiment(message_to_process)
            self.log(f"[{self.proxy_name}] Sentimento detectado: {sentiment_result}")

            # ⏱️ Adiciona timestamps finais
            processed_message = self.register_time_when_go_out(message_to_process)

            # 📤 Envia mensagem com sentimento
            full_message = processed_message + f"SENTIMENTO:;{sentiment_result};"

            self.log(f"[{self.proxy_name}] Mensagem processada. Enviando para destino: {full_message[:50]}...")
            self.send_message_to_destiny(full_message + "\n", self.target_address)

    def analyze_sentiment(self, message: str) -> str:
        try:
            # Extrai apenas o texto da mensagem se ela tiver timestamps ou outros dados
            parts = message.split(';')
            text = parts[0] if parts else message
            
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            
            if polarity > 0.1:
                return "Positivo"
            elif polarity < -0.1:
                return "Negativo"
            else:
                return "Neutro"
        except Exception as e:
            self.log(f"[{self.proxy_name}] Erro ao analisar sentimento: {e}")
            return "Indefinido"


    # def process_and_send_to_destiny(self):
    #     message_to_process = None
        
    #     with self.processing_lock:
    #         if not self.processing_queue:
    #             return
    #         message_to_process = self.processing_queue.pop(0)

    #     if message_to_process:
    #         delay = max(0, random.gauss(self.service_time, self.std)) / 1000.0
    #         time.sleep(delay)

    #         processed_message = self.register_time_when_go_out(message_to_process)
    #         self.log(f"[{self.proxy_name}] Mensagem processada. Enviando para destino: {processed_message[:50]}...")

            
    #         self.send_message_to_destiny(processed_message + "\n", self.target_address)
            
        
    def register_time_when_arrives(self, received_message: str) -> str:
        parts = received_message.split(';')
        
        last_timestamp_str = parts[-1].strip() if parts else ""
        last_timestamp = get_current_millis()

        if last_timestamp_str.isdigit():
            try:
                last_timestamp = int(last_timestamp_str)
            except ValueError:
                self.log(f"[{self.proxy_name}] Aviso: Não foi possível converter timestamp '{last_timestamp_str}' para int. Usando tempo atual.")
        else:
             self.log(f"[{self.proxy_name}] Aviso: Último elemento '{last_timestamp_str}' não é um timestamp válido. Usando tempo atual.")

        time_now = get_current_millis()
        duration = time_now - last_timestamp
        
        received_message += f"{time_now};{duration};"
        return received_message

    def register_time_when_go_out(self, received_message: str) -> str:
       
        time_now = get_current_millis()
        
        parts = received_message.split(';')
        
        arrival_to_service_timestamp_str = parts[-3] if len(parts) >= 3 else str(get_current_millis())
        
        arrival_to_service_timestamp = int(arrival_to_service_timestamp_str) if arrival_to_service_timestamp_str.isdigit() else get_current_millis()

        processing_time = time_now - arrival_to_service_timestamp
        
        try:
            initial_source_timestamp = int(parts[1])
            total_response_time = time_now - initial_source_timestamp
        except (ValueError, IndexError):
            self.log(f"[{self.proxy_name}] Aviso: Não foi possível obter o timestamp inicial da Source para MRT. Usando processing_time como MRT.")
            total_response_time = processing_time
            
        received_message += f"{time_now};{processing_time};RESPONSE TIME:;{total_response_time};"
        return received_message