# Pasid Validator Python

Escrito originalmente em Java, O PASID-VALIDATOR serve para montar um sistema distribuído cliente-servidor(es) e capturar os tempos de cada etapa do processamento. Este projeto reescreve o PASID-VALIDOR na linguagem python, como parte da proposta do trabalho final da disciplina de Sistemas Distribuidos. O projeto é dividido em duas etapas:

* **Fase 1: Reescrita e Implementação da Comunicação via Sockets (Versão Atual)**
    * Foco na tradução da lógica original do Java para Python.
    * **Implementação completa da comunicação entre os componentes utilizando sockets TCP/IP reais.** Isso permite validar o fluxo lógico e os cálculos de tempo em um ambiente mais próximo de uma aplicação distribuída.
* **Fase 2: Execução Distribuída com Docker (Próximos Passos)**
    * Implementação e execução dos componentes em ambientes conteinerizados (Docker).
    * Serão utilizados 1 `Source`, 2 `Load Balancers` e seus respectivos serviços, rodando em contêineres separados para simular um ambiente distribuído real.



### Estrutura do projeto
O projeto reescrito em python possui a seguinte estrutura:

```
pasid_validator_python/
├── src/
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── abstract_proxy.py
│   │   ├── target_address.py
│   │   ├── source.py
│   │   ├── load_balancer_proxy.py
│   │   ├── service_proxy.py
│   │   └── utils.py  
│   ├── tests/
│   │   └── validation/
│   │       ├── __init__.py
│   │       └── local_test_services.py 
├── config/
│   ├── loadbalancer1.properties
│   ├── loadbalancer2.properties
│   └── source.properties
├── run_components/
│   ├── run.sh
│   ├── run_loadbalancer1.py
│   ├── run_loadbalancer2.py
│   ├── run_service1.py
│   ├── run_service2.py
│   └── run_source.py
└── main.py    
```

### Como Funciona (Fase 1 - Comunicação via Sockets)

O projeto é construído em torno de uma arquitetura de **proxies** que gerenciam o fluxo de requisições e o processamento em um ambiente distribuído. Cada componente é uma thread separada, permitindo a execução concorrente e a comunicação em rede.

#### **Componentes Principais e Suas Funções:**

1.  **`Source` (Origem)**
    * **Função:** Atua como o gerador de requisições. Inicia o fluxo de mensagens no sistema e, posteriormente, coleta as respostas finalizadas.
    * **Métricas:** É responsável por calcular o Tempo Médio de Resposta (MRT) de ponta a ponta e, na fase de "alimentação do modelo", extrai os tempos de transição (`T-values`) entre os diferentes estágios da cadeia de processamento.
    * **Configuração:** Seu comportamento é definido por `config/source.properties`, incluindo o número de mensagens a enviar e o destino inicial.

2.  **`LoadBalancerProxy` (Balanceador de Carga)**
    * **Função:** Recebe requisições e as distribui eficientemente para um grupo de "serviços" (que podem ser outras instâncias de `LoadBalancerProxy` ou `ServiceProxy` no nível final).
    * **Comportamento:** Simula o roteamento de mensagens, a gerência de filas (com capacidade configurável) e o controle de quais serviços estão disponíveis para receber novas requisições através de "pings".
    * **Configuração:** `config/loadbalancer1.properties` e `config/loadbalancer2.properties` definem suas portas, tamanho da fila, número de serviços que gerenciam e para onde os serviços devem rotear suas respostas.

3.  **`ServiceProxy` (Serviço)**
    * **Função:** Representa uma unidade de trabalho que processa uma requisição.
    * **Simulação:** Após receber uma mensagem, simula um tempo de processamento (baseado em um tempo de serviço e desvio padrão configuráveis) e, em seguida, envia a mensagem para o próximo destino na cadeia (que pode ser outro `LoadBalancerProxy` ou a `Source` novamente).

#### **Comunicação entre Componentes (Fase 1):**

Nesta fase, a comunicação é realizada através de **sockets TCP/IP reais**. Isso significa que:

* **Sockets de Rede:** Os componentes utilizam o módulo `socket` do Python para estabelecer conexões TCP/IP.
* **Comunicação Persistente:** As conexões são mantidas abertas quando possível para permitir comunicação bidirecional contínua (ex: para pings e respostas).
* **Fluxo de Dados:** Mensagens são enviadas e recebidas como strings via rede.

#### **Fluxo de Requisições Típico na Fase 1:**

1.  **`Source`** inicia uma conexão TCP/IP com o `LoadBalancerProxy 1` (porta 2000).
2.  **`Source`** gera uma mensagem com um timestamp inicial e a envia para o `LoadBalancerProxy 1` através da conexão.
3.  **`LoadBalancerProxy 1`** recebe a mensagem, a coloca em sua fila e, quando um serviço está disponível, a encaminha para um de seus `ServiceProxy`s internos (ex: `ServiceProxy 1` na porta 2001).
4.  O `ServiceProxy` (gerenciado por LB1) simula o processamento e estabelece uma nova conexão (ou utiliza uma existente) para enviar a mensagem processada para o **`LoadBalancerProxy 2`** (porta 3000).
5.  **`LoadBalancerProxy 2`** recebe a mensagem e a distribui para um de seus `ServiceProxy`s internos (ex: `ServiceProxy 3` na porta 3001).
6.  O `ServiceProxy` (gerenciado por LB2) simula o processamento e estabelece uma nova conexão (ou utiliza uma existente) para enviar a mensagem de volta para o **`Source`** (porta 1025).
7.  A `Source` recebe a mensagem finalizada através de sua porta de escuta, calcula o tempo total de resposta e os T-values (tempos de transição entre os componentes) e os loga.

---

#### **Como executar o sistema:**

Para executar o sistema, você pode utilizar o script `run.sh` no diretório `run_components` ou iniciar cada componente em um terminal diferente.


Dentro da raiz do projeto, execute:

```bash
cd run_components/
./run.sh
```

O arquivo run.sh foi implementado apenas para facilitar a inicialização dos componentes para os testes, dessa forma não seria necessário executar manualmente cada componente separadamente.

---

### Tecnologias Utilizadas

* **Python 3.12.3**: Linguagem de programação principal.
* **`threading`**: Módulo Python para lidar com concorrência e execução de componentes em threads separadas.
* **`socket`**: Módulo Python para comunicação de rede.
* **(Próxima Etapa) Docker**: Para conteinerização dos componentes na Etapa 2.

---

### Autores

* [@NaraAndrad3](https://github.com/NaraAndrad3)

---