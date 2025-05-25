
import threading
import time
import sys
import os 
from collections import OrderedDict

from src.domain.abstract_proxy import AbstractProxy
from src.domain.target_address import TargetAddress
from src.domain.utils import read_properties_file, get_current_millis

from src.domain.service_proxy import ServiceProxy 

class Source(AbstractProxy):
    """
    A classe Source atua como o gerador de requisições e o ponto final para as respostas
    no sistema distribuído simulado. Ela é a "origem" das mensagens, responsável
    por iniciar o fluxo de comunicação e coletar métricas de desempenho.
    """
    
    def __init__(self, properties_path: str):
        """
        Construtor da classe Source.
        Inicializa o Source lendo as configurações de um arquivo de propriedades.

        Args:
            properties_path (str): O caminho para o diretório que contém o arquivo 'source.properties'.
        """
        # Chama o construtor da classe pai (AbstractProxy) com o nome "source" e porta 0.
        # A porta 0 é usada na simulação em memória, pois o Source não escuta diretamente conexões
        # da mesma forma que um LoadBalancer ou ServiceProxy.
        super().__init__("source", 0) 

        self.properties_path = properties_path
        self.log_writer = None # Objeto para escrever no arquivo de log
        self.init_log_file() # Inicializa o arquivo de log (log.txt)

        # Lê as propriedades do arquivo 'source.properties' localizado no caminho fornecido.
        props = read_properties_file(f"{properties_path}/source.properties")

        # Configurações principais do Source baseadas nas propriedades
        self.model_feeding_stage = props.get("modelFeedingStage").lower() == 'true'
        self.proxy_name = "origem" # Nome do proxy, alterado para português
        self.local_port = int(props.get("sourcePort")) # Porta local do Source
        
        # Endereço do primeiro destino para o qual o Source enviará mensagens 
        self.target_address = TargetAddress(
            props.get("targetIp"),
            int(props.get("targetPort"))
        )
        # Número máximo de mensagens esperadas para serem consideradas nos cálculos de métricas
        self.max_considered_messages_expected = int(props.get("maxConsideredMessagesExpected"))

        # Listas de Tempos Médios de Resposta (MRTs) e Desvios Padrão (SDVs) do modelo,
        # usados na fase de validação (se implementada) para comparação.
        mrts_array = props.get("mrtsFromModel", "").split(',')
        self.mrts_from_model = [float(mrt.strip()) for mrt in mrts_array if mrt.strip()]

        sdvs_array = props.get("sdvsFromModel", "").split(',')
        self.sdvs_from_model = [float(sdv.strip()) for sdv in sdvs_array if sdv.strip()]

        # Configurações para variação de serviços (usado para reconfigurar Load Balancers dinamicamente)
        self.arrival_delay = int(props.get("variatingServices.arrivalDelay")) # Atraso entre o envio de mensagens (em ms)
        self.variated_server_load_balancer_ip = props.get("variatingServices.variatedServerLoadBalancerIp")
        self.variated_server_load_balancer_port = int(props.get("variatingServices.variatedServerLoadBalancerPort"))

        # Lista de quantidades de serviços a serem variadas durante a simulação
        qtd_services_array = props.get("variatingServices.qtdServices", "").split(',')
        self.qtd_services = [int(q.strip()) for q in qtd_services_array if q.strip()]

        # Variáveis de estado para controlar o progresso da simulação
        self.cycles_completed = [False] * len(self.qtd_services) # Rastreia quais ciclos de variação de serviço foram concluídos
        self.all_cycles_completed = False # Flag para indicar se todos os ciclos de variação foram completados

        self.considered_messages = [] # Lista para armazenar as mensagens de resposta consideradas para análise
        self.source_current_index_message = 1 # Contador do índice da mensagem atual a ser enviada
        self.dropp_count = 0 # Contador de mensagens descartadas na origem

        self.experiment_data = [] # Lista para armazenar dados experimentais (ex: MRTs calculados)
        self.experiment_error = [] # Lista para armazenar erros experimentais (ex: desvios padrão)

        # Configuração de um mecanismo de timeout (para futuras entregas ou cenários mais complexos)
        self.timeout_duration = 30000 # Duração do timeout em milissegundos (30 segundos)
        self.timeout_future = None # Objeto para controlar o agendamento do timeout
        self.is_timeout_triggered = False # Flag para indicar se o timeout foi acionado

        # Registra esta instância do Source no registro global de proxies.
        # Isso permite que outros componentes do sistema (Load Balancers, Services)
        # possam encontrar e enviar mensagens de volta para o Source.
        AbstractProxy.register_proxy(self)

        # Imprime os parâmetros de configuração do Source no início da execução.
        self.print_source_parameters()

    def init_log_file(self):
        """
        Inicializa o arquivo de log 'log.txt'.
        Se o arquivo já existir, ele é removido antes de ser aberto para garantir um log limpo a cada execução.
        O arquivo é aberto no modo de 'append' ('a') com codificação UTF-8.
        """
        try:
            log_file_path = "log.txt"
            if os.path.exists(log_file_path):
                os.remove(log_file_path) # Remove o arquivo de log existente
            self.log_writer = open(log_file_path, 'a', encoding='utf-8') # Abre para escrita em modo append
        except OSError as e:
            # Em caso de erro ao inicializar o arquivo de log, imprime uma mensagem de erro
            # e define log_writer como None para evitar futuras tentativas de escrita.
            print(f"ERRO: Erro ao inicializar o arquivo de log: {e}", file=sys.stderr)
            self.log_writer = None # Fallback: não haverá log em arquivo

    def log(self, message: str):
        """
        Escreve uma mensagem tanto no console quanto no arquivo de log (se estiver disponível).

        Args:
            message (str): A mensagem a ser logada.
        """
        print(message) # Imprime a mensagem no console
        if self.log_writer: # Verifica se o escritor de log está ativo
            try:
                self.log_writer.write(message + "\n") # Escreve a mensagem no arquivo
                self.log_writer.flush() # Garante que a mensagem seja escrita imediatamente no disco
            except OSError as e:
                # Em caso de erro de escrita no arquivo de log, imprime uma mensagem de erro
                # e desativa o log em arquivo para evitar mais erros.
                print(f"ERRO: Erro ao escrever no arquivo de log: {e}", file=sys.stderr)
                self.log_writer = None # Desativa o log em arquivo

    def print_source_parameters(self):
        """
        Imprime (e loga) todos os parâmetros de configuração do Source.
        Útil para depuração e para ter um resumo das configurações no início da simulação.
        """
        self.log("")
        self.log("======================================")
        self.log("Parâmetros da Origem:")
        self.log(f"Caminho das Propriedades: {self.properties_path}")
        self.log(f"Fase de Alimentação do Modelo: {self.model_feeding_stage}")
        self.log(f"Porta da Origem: {self.local_port}")
        self.log(f"IP do Destino: {self.target_address.get_ip()}")
        self.log(f"Porta do Destino: {self.target_address.get_port()}")
        self.log(f"Máximo de Mensagens Consideradas Esperadas: {self.max_considered_messages_expected}")
        self.log(f"MRTs do Modelo: {self.mrts_from_model}")
        self.log(f"SDVs do Modelo: {self.sdvs_from_model}")
        self.log(f"Atraso de Chegada: {self.arrival_delay}ms")
        self.log(f"Quantidade de Serviços a Variar: {self.qtd_services}")
        self.log("======================================")

    def close_log(self):
        """
        Fecha o arquivo de log.
        Deve ser chamado ao final da execução da simulação para garantir que todos os dados sejam salvos.
        """
        if self.log_writer:
            self.log_writer.close()

    def run(self):
        """
        Método principal da thread do Source.
        Determina qual fase da simulação (alimentação do modelo ou validação) será executada.
        """
        print("Iniciando a Origem...")
        try:
            if self.model_feeding_stage:
                # Se estiver na fase de alimentação do modelo, gera dados para treinamento.
                self.send_message_feeding_stage()
            else:
                # Caso contrário, executa a fase de validação do modelo.
                self.send_messages_validation_stage()
        except Exception as e:
            # Captura e loga qualquer erro inesperado durante a execução principal.
            self.log(f"ERRO na execução da Origem: {e}")
            import traceback
            traceback.print_exc() # Imprime o stack trace completo para depuração
        finally:
            self.close_log() # Garante que o arquivo de log seja fechado ao final

    def send_message_feeding_stage(self):
        """
        Implementa a lógica para a "fase de alimentação do modelo".
        Nesta fase, um número fixo de requisições é gerado para coletar dados de temporização
        (os "T-values") que podem ser usados para calibrar um modelo de desempenho.
        """
        # Sobrescreve o atraso de chegada para 2000ms, conforme o comportamento original do código Java.
        self.arrival_delay = 2000 
        self.log("ATENÇÃO: Garanta que o atraso de chegada seja um valor maior que a soma de todos os tempos de serviço.")
        self.log("##############################")
        self.log("Fase de Alimentação do Modelo Iniciada")
        self.log("##############################")
        self.log(f"Apenas 10 requisições serão geradas com Atraso de Chegada (AD) = {self.arrival_delay}ms")

        time.sleep(5) # Espera 5 segundos antes de começar a enviar mensagens

        # Loop para gerar e enviar 10 mensagens
        for j in range(1, 11):
            # Formato da mensagem: "ID_CLIENTE;INDEX_MENSAGEM;TIMESTAMP_ENVIO;"
            # O '1' inicial pode ser um ID de cliente padrão.
            msg = f"1;{self.source_current_index_message};{get_current_millis()};"
            try:
                self._send(msg) # Tenta enviar a mensagem para o destino
            except Exception as e:
                self.log(f"ERRO ao enviar mensagem na fase de alimentação: {e}")
                sys.exit(1) # Sai da simulação em caso de erro crítico de envio
            self.source_current_index_message += 1 # Incrementa o índice da mensagem
            time.sleep(self.arrival_delay / 1000.0) # Aguarda o atraso de chegada em segundos

        # Após enviar todas as mensagens, o Source entra em um loop de espera
        # para aguardar o retorno das mensagens processadas pelo sistema.
        print("Aguardando as mensagens serem processadas...")
        while True:
            time.sleep(1) # Apenas espera; as respostas são tratadas pelo método 'receiving_messages'

    def send_messages_validation_stage(self):
        """
        Método placeholder para a fase de validação do modelo.
        Nesta entrega, esta fase não está implementada. Em uma versão completa,
        envolveria a geração de mensagens com base em taxas de chegada controladas
        e a comparação dos MRTs experimentais com os MRTs preditos pelo modelo.
        """
        self.log("A Fase de Validação não está implementada nesta entrega.")
        self.log("Saindo, pois a fase de validação não é o foco desta entrega.")
        sys.exit(0) # Encerra a simulação

    def _send_message_to_configure_server(self, config_message: str):
        """
        Simula o envio de uma mensagem de configuração para um LoadBalancerProxy.
        Este método é usado para modificar dinamicamente o número de serviços gerenciados
        por um Load Balancer específico.

        Args:
            config_message (str): A mensagem de configuração a ser enviada.
        """
        # Procura a instância do LoadBalancerProxy pelo seu número de porta registrado.
        target_lb_proxy = AbstractProxy.get_proxy_by_port(self.variated_server_load_balancer_port)
        if target_lb_proxy:
            print(f"[{self.proxy_name}] Enviando mensagem de configuração para o Balanceador de Carga na porta {self.variated_server_load_balancer_port}")
            # Na simulação em memória, a comunicação é simulada chamando diretamente
            # o método receiving_messages() do Load Balancer.
            target_lb_proxy.receiving_messages(config_message) 
            print(f"[{self.proxy_name}] Mensagem de configuração simulada enviada e assumida como reconhecida.")
        else:
            # Levanta um erro se o Load Balancer de destino não for encontrado.
            raise RuntimeError(f"Não foi possível encontrar o LoadBalancerProxy na porta {self.variated_server_load_balancer_port} para configuração.")

    def _send(self, msg: str):
        """
        Simula o envio de uma mensagem do Source para o seu destino (geralmente o primeiro Load Balancer).
        Verifica se o destino está livre antes de enviar. Se o destino estiver ocupado,
        a mensagem é "descartada na origem" e o Source espera o atraso de chegada.

        Args:
            msg (str): A mensagem a ser enviada.
        """
        if self.is_destiny_free(self.target_address):
            # Se o destino estiver livre, envia a mensagem.
            self.send_message_to_destiny(msg, self.target_address)
        else:
            # Se o destino estiver ocupado, a mensagem é descartada.
            self.log(f"DESCARTADA NA ORIGEM: {msg}")
            self.dropp_count += 1 # Incrementa o contador de mensagens descartadas
            # Conforme o comportamento do código Java, se a mensagem é descartada,
            # o Source ainda espera o atraso de chegada antes de tentar novamente ou enviar a próxima.
            time.sleep(self.arrival_delay / 1000.0)

    def receiving_messages(self, received_message: str):
        """
        Lida com as mensagens de entrada (respostas) que chegam ao Source vindo do sistema distribuído.
        Este método é chamado quando o Source recebe uma mensagem de volta (uma resposta finalizada).

        Args:
            received_message (str): A mensagem recebida.
        """
        if received_message is None:
            return # Ignora mensagens nulas

        # Primeiro, processa a mensagem para calcular e anexar o Tempo Médio de Resposta (MRT) final.
        processed_message = self._register_mrt_at_the_end_source(received_message) 
        
        # Delega o processamento posterior da resposta com base na fase da simulação.
        if self.model_feeding_stage:
            # Se estiver na fase de alimentação, executa a lógica de coleta de T-values.
            self.execute_first_stage_of_model_feeding(processed_message) 
        else:
            # Se estiver na fase de validação, executa a lógica correspondente (atualmente não implementada).
            self.execute_second_stage_of_validation(processed_message)

    def _register_mrt_at_the_end_source(self, received_message: str) -> str:
        """
        Calcula e registra o Tempo Médio de Resposta (MRT) final da mensagem
        quando ela retorna ao Source. O MRT é a duração total que a mensagem
        levou desde o seu envio inicial até o seu retorno.

        Args:
            received_message (str): A mensagem recebida, contendo os timestamps intermediários.

        Returns:
            str: A mensagem original com o MRT final anexado.
        """
        parts = received_message.split(';')
        
        # Assume que o penúltimo elemento é o timestamp de saída do último serviço,
        # e o terceiro elemento é o timestamp de envio inicial do Source.
        last_timestamp_str = parts[-2]
        first_timestamp_str = parts[2]

        try:
            last_timestamp = int(last_timestamp_str)
            first_timestamp = int(first_timestamp_str)
        except (ValueError, IndexError):
            # Se houver um erro ao analisar os timestamps, loga o erro e retorna a mensagem original.
            self.log(f"ERRO ao analisar timestamps para MRT: {received_message}. Pulando cálculo de MRT.")
            return received_message 

        current_mrt = last_timestamp - first_timestamp # Cálculo do MRT
        # Anexa a label "RESPONSE TIME:" e o valor do MRT à mensagem.
        received_message += f"TEMPO DE RESPOSTA:;{current_mrt};" 
        return received_message

    def execute_first_stage_of_model_feeding(self, received_message: str):
        """
        Processa as mensagens de resposta durante a fase de alimentação do modelo.
        Coleta os tempos de transição (T-values) e, em um ponto específico (quando a segunda
        mensagem processada é recebida), calcula as médias desses T-values e encerra a simulação.

        Args:
            received_message (str): A mensagem de resposta recebida e já com o MRT final.
        """
        self.considered_messages.append(received_message) # Adiciona a mensagem à lista de mensagens consideradas
        self.log(received_message) # Loga a mensagem completa recebida

        try:
            # Extrai o índice da mensagem para determinar o ponto de cálculo dos T-values.
            index_from_message = int(received_message.split(";")[1])
        except (ValueError, IndexError):
            self.log(f"ERRO ao analisar o índice da mensagem: {received_message}")
            return 
        
        # A lógica original do Java parece triggar o cálculo no recebimento da mensagem de índice 2.
        if index_from_message == 2: 
            self.log("Acionando o cálculo de T1-T5...")
            time.sleep(1) # Pequeno atraso para garantir que todos os logs anteriores sejam exibidos

            # OrderedDict é usado para manter a ordem dos T-values, como no Java.
            durations_map = OrderedDict() # (Variável não usada diretamente, mas mantém a ideia original)
            
            # Dicionário para armazenar as durações extraídas para cada T-value.
            extracted_durations = {f"T{k}": [] for k in range(1, 6)} # T1, T2, T3, T4, T5
            
            for message_str in self.considered_messages:
                values = message_str.split(";")
                
                # Validação para garantir que a mensagem tem comprimento suficiente para extrair todos os T-values.
                # O número 17 é um palpite baseado no formato de mensagem Java que acumula timestamps.
                if len(values) < 17: 
                    self.log(f"AVISO: Mensagem muito curta para extração completa dos valores T: {message_str}. Tamanho: {len(values)}")
                    continue
                
                try:
                    # Extrai os valores de duração dos tempos de transição (T-values)
                    # T1: Tempo de rede do Source para o primeiro Load Balancer.
                    extracted_durations["T1"].append(int(values[4]))
                    # T2: Tempo de processamento do primeiro Load Balancer.
                    extracted_durations["T2"].append(int(values[7]))
                    # T3: Tempo de rede do primeiro Load Balancer para o segundo Load Balancer.
                    extracted_durations["T3"].append(int(values[10]))
                    # T4: Tempo de processamento do segundo Load Balancer.
                    extracted_durations["T4"].append(int(values[13]))
                    # T5: Tempo de rede do segundo Load Balancer de volta ao Source.
                    extracted_durations["T5"].append(int(values[16]))
                except (ValueError, IndexError) as e:
                    self.log(f"ERRO ao extrair valores T da mensagem '{message_str}': {e}")
                    continue

            # Calcula a média das durações para cada T-value.
            final_averages = OrderedDict()
            for key, durations in extracted_durations.items():
                if durations:
                    avg = sum(durations) / len(durations)
                    final_averages[key] = avg
                else:
                    final_averages[key] = 0.0 # Define 0.0 se não houver durações (evita divisão por zero)

            self.log("Os tempos para alimentar as transições do modelo são os seguintes:")
            for key, avg_value in final_averages.items():
                self.log(f"{key} = {avg_value}")
            
            self.log("Fase de Alimentação do Modelo concluída. Saindo da simulação.")
            sys.exit(0) # Encerra a simulação após o cálculo dos T-values.

    def execute_second_stage_of_validation(self, received_message: str):
        """
        Método placeholder para a lógica da fase de validação.
        Nesta entrega, ele apenas indica que a lógica não está implementada.
        Em uma versão completa, esta fase usaria o modelo treinado para prever
        o desempenho e comparar com os resultados experimentais.

        Args:
            received_message (str): A mensagem de resposta recebida.
        """
        self.log("A lógica da Fase de Validação não está implementada nesta entrega.")

    def create_connection_with_destiny(self):
        """
        Sobrescreve o método abstrato da classe pai.
        Na simulação em memória, o Source não estabelece conexões de socket diretas com seus destinos.
        A comunicação é feita através do registro interno de proxies.
        """
        pass # Nenhuma ação é necessária para a simulação em memória

    def _simulate_is_free(self) -> bool:
        """
        Sobrescreve o método _simulate_is_free da classe AbstractProxy.
        O Source é sempre considerado livre para receber mensagens, pois ele atua como
        o coletor final de respostas e não tem uma "fila de processamento" que possa ficar cheia.

        Returns:
            bool: Sempre retorna True, indicando que o Source está sempre disponível para receber.
        """
        return True

# Bloco de código para garantir que o diretório 'config' exista.
# Isso é útil para armazenar arquivos de propriedades que configuram a simulação.
script_dir = os.path.dirname(__file__) # Obtém o diretório do script atual
config_dir = os.path.join(script_dir, "../../config") # Constrói o caminho para o diretório 'config' (dois níveis acima)
if not os.path.exists(config_dir):
    os.makedirs(config_dir) # Cria o diretório 'config' se ele não existir