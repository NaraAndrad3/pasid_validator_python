import threading
import time
import sys
import os
from collections import OrderedDict
import socket

from src.domain.abstract_proxy import AbstractProxy
from src.domain.target_address import TargetAddress
from src.domain.utils import read_properties_file, get_current_millis, calculate_std_dev, calculate_mean
import matplotlib.pyplot as plt
from collections import defaultdict

class Source(AbstractProxy):
    """
    A classe Source gera dados sintéticos (mensagens) e interage com os Load Balancers,
    atuando como a origem das requisições e o receptor final das respostas processadas.
    """

    def __init__(self, properties_path: str):
        self.experiment_config = []
        props = read_properties_file(properties_path)

        self.model_feeding_stage = props.get("modelFeedingStage", "false").lower() == 'true'

        source_port = int(props.get("sourcePort"))
        target_ip = props.get("targetIp")
        target_port = int(props.get("targetPort"))
        
        super().__init__("Source", source_port, TargetAddress(target_ip, target_port))

        self.max_considered_messages_expected = int(props.get("maxConsideredMessagesExpected"))
        self.arrival_delay = int(props.get("variatingServices.arrivalDelay")) 
        
        self.variated_server_load_balancer_ip = props.get("variatingServices.variatedServerLoadBalancerIp")
        self.variated_server_load_balancer_port = int(props.get("variatingServices.variatedServerLoadBalancerPort"))
        
        self.qtd_services = [int(q) for q in props.get("variatingServices.qtdServices").split(',')]
        self.mrts_from_model = [float(m) for m in props.get("mrtsFromModel").split(',')]
        self.sdvs_from_model = [float(s) for s in props.get("sdvsFromModel").split(',')]

        self.source_current_index_message = 0
        self.dropp_count = 0
        self.all_cycles_completed = False
        
        self.considered_messages = []
        self.current_cycle_index = 0
        self.experiment_data = []
        self.experiment_error = []

        self.messages_per_cycle = [int(m) for m in props.get("variatingServices.messagesPerCycle").split(',')]
        
        self.print_source_parameters()

    def print_source_parameters(self):
        self.log("======================================")
        self.log("Parâmetros da Origem:")
        self.log(f"Nome do Proxy: {self.proxy_name}")
        self.log(f"Porta Local: {self.local_port}")
        self.log(f"Destino Principal (Primeiro LB): {self.target_address.get_ip()}:{self.target_address.get_port()}")
        self.log(f"Estágio de Alimentação do Modelo: {self.model_feeding_stage}")
        self.log(f"Atraso de Chegada (ms): {self.arrival_delay}")
        self.log(f"Máximo de Mensagens Esperadas por Ciclo: {self.max_considered_messages_expected}")
        self.log(f"Servidor Balanceador Variável (IP:Porta): {self.variated_server_load_balancer_ip}:{self.variated_server_load_balancer_port}")
        self.log(f"Qtd. de Serviços por Ciclo: {self.qtd_services}")
        self.log(f"MRTs do Modelo: {self.mrts_from_model}")
        self.log(f"SDVs do Modelo: {self.sdvs_from_model}")
        self.log("======================================")

    def run(self):
        self.log("Iniciando a Origem...")
       
        try:
            if self.model_feeding_stage:
                self.send_message_feeding_stage()
            else:
                self.send_messages_validation_stage()
        except Exception as e:
            self.log(f"ERRO na execução da Origem: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop_proxy() 

    def _send(self, msg: str):
        try:
            message_with_delimiter = msg + "\n" 
            self.send_message_to_destiny(message_with_delimiter, self.target_address)
        except Exception as e:
            self.log(f"ERRO ao enviar mensagem para {self.target_address.get_ip()}:{self.target_address.get_port()}: {e}")
            self.dropp_count += 1
        
        time.sleep(self.arrival_delay / 1000.0) 

    def _send_config_message(self, target_address: TargetAddress, config_message: str):
        try:
            message_with_delimiter = config_message + "\n"
            self.send_message_to_destiny(message_with_delimiter, target_address)
            self.log(f"[{self.proxy_name}] Mensagem de configuração enviada para {target_address}: '{config_message}'")
        except Exception as e:
            self.log(f"[{self.proxy_name}] ERRO ao enviar mensagem de configuração para {target_address}: {e}")

    # def send_message_feeding_stage(self):
    #     self.log("[Stage] Alimentação do Modelo: Iniciado.")
    #     message_index = 0
    #     MAX_MESSAGES_TO_SEND = 5 
    #     while self.is_running and message_index < MAX_MESSAGES_TO_SEND:
    #         message = f"{message_index};{get_current_millis()};" 
    #         self._send(message)
    #         message_index += 1
    #         if message_index % 100 == 0:
    #             self.log(f"[{self.proxy_name}] Enviadas {message_index} mensagens no estágio de alimentação.")
    #     self.log(f"[{self.proxy_name}] Estágio de alimentação finalizado após enviar {message_index} mensagens.")

    def send_message_feeding_stage(self):
        self.log("[Stage] Alimentação do Modelo: Iniciado.")

        messages = [
            "Estou muito feliz com o resultado!",
            "O serviço foi péssimo e decepcionante.",
            "Nada de especial aconteceu hoje.",
            "A comida estava maravilhosa, adorei!",
            "Estou me sentindo cansado e desmotivado.",
            "Foi um dia comum, sem novidades.",
            "O atendimento foi ótimo e muito rápido!",
            "O produto chegou danificado e me deixou frustrado.",
            "Não tenho opinião formada sobre isso.",
            "A experiência foi incrível, recomendo para todos!",
        ]

        MAX_MESSAGES_TO_SEND = len(messages)
        message_index = 0

        while self.is_running and message_index < MAX_MESSAGES_TO_SEND:
            message = f"{messages[message_index]};{get_current_millis()};"
            self._send(message)
            message_index += 1
            if message_index % 5 == 0:
                self.log(f"[{self.proxy_name}] Enviadas {message_index} mensagens no estágio de alimentação.")

        self.log(f"[{self.proxy_name}] Estágio de alimentação finalizado após enviar {message_index} mensagens.")

 
    def send_messages_validation_stage(self):
        self.log("[Stage] Validação: Iniciado.")

        for qtd_services_for_cycle in self.qtd_services:
            for num_msgs in self.messages_per_cycle:
                self.max_considered_messages_expected = num_msgs  # atualiza dinamicamente

                self.log(f"\n[{self.proxy_name}] Iniciando ciclo com {qtd_services_for_cycle} serviço(s) e {num_msgs} mensagens.")

                # Reconfigura LB2
                variated_lb_address = TargetAddress(
                    self.variated_server_load_balancer_ip,
                    self.variated_server_load_balancer_port
                )
                config_message = f"config;{qtd_services_for_cycle}"
                self._send_config_message(variated_lb_address, config_message)
                time.sleep(2)

                # Reseta dados para o novo ciclo
                self.considered_messages.clear()
                self.source_current_index_message = 0

                # Fecha conexão anterior com LB1
                try:
                    with self._outbound_connections_lock:
                        target_key = (self.target_address.get_ip(), self.target_address.get_port())
                        if target_key in self._outbound_connections:
                            self.log(f"[{self.proxy_name}] Fechando conexão existente para {target_key} antes do novo ciclo.")
                            self._outbound_connections[target_key].close()
                            del self._outbound_connections[target_key]
                except Exception as e:
                    self.log(f"[{self.proxy_name}] Erro ao fechar conexão com LB1: {e}")

                # Envia as mensagens para esse ciclo
                while self.source_current_index_message < self.max_considered_messages_expected and self.is_running:
                    message = f"{self.source_current_index_message};{get_current_millis()};"
                    self._send(message)
                    self.source_current_index_message += 1

                    if self.source_current_index_message % 10 == 0:
                        self.log(f"[{self.proxy_name}] Enviadas {self.source_current_index_message} mensagens no ciclo atual.")

                self.log(f"[{self.proxy_name}] Aguardando {self.max_considered_messages_expected} respostas...")
                wait_start_time = time.time()
                WAIT_TIMEOUT_SECONDS = 120

                while (len(self.considered_messages) < self.max_considered_messages_expected
                    and self.is_running
                    and (time.time() - wait_start_time) < WAIT_TIMEOUT_SECONDS):
                    time.sleep(0.1)

                if len(self.considered_messages) >= self.max_considered_messages_expected:
                    self.log(f"[{self.proxy_name}] Todas as {self.max_considered_messages_expected} mensagens retornaram.")
                else:
                    self.log(f"[{self.proxy_name}] ATENÇÃO: Apenas {len(self.considered_messages)} de {self.max_considered_messages_expected} mensagens retornaram.")

                self.experiment_config.append((qtd_services_for_cycle, num_msgs))
                self.execute_second_stage_of_validation_metrics()

        self.all_cycles_completed = True
        self.log("[Stage] Validação: Finalizado. Todos os ciclos concluídos.")
        self.display_final_results()

    def receiving_messages(self, received_message: str,conn: socket.socket):
        if received_message is None or received_message.strip() == "":
            return

        message_stripped = received_message.strip()
        
        if message_stripped == "ping":
            self.log(f"[{self.proxy_name}] Recebido ping.")
            return

        self.log(f"[{self.proxy_name}] Mensagem de resposta recebida: {message_stripped}...")
        self.considered_messages.append(message_stripped)

    def _simulate_is_free(self) -> bool:
        return True 

    def _register_mrt_at_the_end_source(self, received_message):
        return received_message 

    def execute_first_stage_of_model_feeding(self, processed_message: str = ""): 
        pass

    def execute_second_stage_of_validation_metrics(self):
        if not self.considered_messages:
            self.log(f"[{self.proxy_name}] Nenhuma mensagem retornou para o ciclo {self.current_cycle_index + 1}. Não é possível calcular MRT/SDV.")
            self.experiment_data.append(0.0) 
            self.experiment_error.append(0.0) 
            return

        mrts = self._extract_mrts(self.considered_messages)
        if not mrts:
            self.log(f"[{self.proxy_name}] Nenhuma MRT válida extraída das mensagens retornadas para o ciclo {self.current_cycle_index + 1}.")
            self.experiment_data.append(0.0)
            self.experiment_error.append(0.0)
            return

        mrt_from_experiment = calculate_mean(mrts)
        standard_deviation = calculate_std_dev(mrts, mrt_from_experiment)

        self.display_results(mrt_from_experiment, standard_deviation)
        self.log(f"[{self.proxy_name}] Ciclo {self.current_cycle_index + 1} Concluído. MRT Experimental: {mrt_from_experiment:.2f}ms, SD Experimental: {standard_deviation:.2f}ms")

    def _extract_mrts(self, messages: list[str]) -> list[float]:
        mrts = []
        for message in messages:
            mrt = self._parse_mrt(message)
            if mrt is not None:
                mrts.append(mrt)
        return mrts

    def _parse_mrt(self, message: str) -> float | None:
        parts = message.split(';')
        try:
            if "RESPONSE TIME:" in parts:
                idx = parts.index("RESPONSE TIME:")
                if idx + 1 < len(parts):
                    return float(parts[idx + 1])
        except (ValueError, IndexError):
            self.log(f"[{self.proxy_name}] Não foi possível parsear MRT de: '{message}'")
        return None

    def display_results(self, mrt_from_experiment: float, standard_deviation: float):
        self.log(f"MRT From Experiment: {mrt_from_experiment:.2f}; SD From Experiment: {standard_deviation:.2f}")
        self.experiment_data.append(mrt_from_experiment)
        self.experiment_error.append(standard_deviation)

    def display_final_results(self):
        self.log("\n======================================")
        self.log("Resultados Finais da Simulação:")

        # Dicionário que agrupa resultados por qtd de serviços
        resultados_por_qtd_servicos = defaultdict(dict)

        for i, mrt_exp in enumerate(self.experiment_data):
            sd_exp = self.experiment_error[i]
            try:
                qtd_serv, num_msgs = self.experiment_config[i]
            except IndexError:
                self.log(f"[{self.proxy_name}] Erro: índice {i} fora do range em experiment_config.")
                continue

            resultados_por_qtd_servicos[qtd_serv][num_msgs] = mrt_exp

            mrt_model = self.mrts_from_model[i] if i < len(self.mrts_from_model) else "N/A"
            sd_model = self.sdvs_from_model[i] if i < len(self.sdvs_from_model) else "N/A"
            self.log(f"Ciclo {i + 1} (Qtd Serviços: {qtd_serv}):")
            self.log(f"  MRT Experimental: {mrt_exp:.2f}ms, SD Experimental: {sd_exp:.2f}ms")
            self.log(f"  MRT do Modelo: {mrt_model}, SD do Modelo: {sd_model}")

        self.log(f"Mensagens descartadas na Origem: {self.dropp_count}")
        self.log("======================================")

        # === Gerar o gráfico final agrupado por qtd de serviços ===
        plt.figure(figsize=(10, 6))
        for qtd_servicos, resultados in sorted(resultados_por_qtd_servicos.items()):
            frases = sorted(resultados.keys())
            mrt_ms = [resultados[qtd] for qtd in frases]
            plt.plot(frases, mrt_ms, marker='o', label=f'{qtd_servicos} serviço(s)')

        plt.title("Tempo Médio de Resposta (MRT) por Quantidade de Mensagens")
        plt.xlabel("Quantidade de Mensagens por Ciclo")
        plt.ylabel("MRT (ms)")
        plt.legend(title="Qtd. Serviços")
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()

        os.makedirs("logs", exist_ok=True)
        plt.savefig("logs/mrt_por_num_mensagens.png")
        plt.show()