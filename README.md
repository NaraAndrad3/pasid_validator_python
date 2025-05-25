# Pasid Validator Python

Escrito originalmente em Java, O PASID-VALIDATOR serve para montar um sistema distribuído cliente-servidor(es) e capturar os tempos de cada etapa do processamento. Este projeto reescreve o PASID-VALIDOR na linguagem python, como parte da proposta do trabalho final da disciplina de Sistemas Distribuidos. O projeto é dividido em duas etapas:

* **Etapa 1: Reescrita e Simulação em Memória (Entrega Atual)**
    * Foco na tradução da lógica original do Java para Python.
    * A comunicação entre os componentes é simulada diretamente em memória, sem o uso de sockets de rede reais. Isso permite validar o fluxo lógico e os cálculos de tempo de forma controlada.
* **Etapa 2: Execução Distribuída com Docker (Próximos Passos)**
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
└── main.py    
```

### Como Funciona (Entrega 01 - Simulação em Memória)

O projeto é construído em torno de uma arquitetura de **proxies** que simulam o fluxo de requisições e o processamento em um ambiente distribuído. Cada componente é uma thread separada, permitindo a execução concorrente.

#### **Componentes Principais e Suas Funções:**

1.  **`Source` (Origem)**
    * **Função:** Atua como o gerador de requisições. Inicia o fluxo de mensagens no sistema e, posteriormente, coleta as respostas finalizadas.
    * **Métricas:** É responsável por calcular o Tempo Médio de Resposta (MRT) de ponta a ponta e, na fase de "alimentação do modelo", extrai os tempos de transição (`T-values`) entre os diferentes estágios da cadeia de processamento.
    * **Configuração:** Seu comportamento é definido por `config/source.properties`, incluindo o número de mensagens a enviar e o destino inicial.

2.  **`LoadBalancerProxy` (Balanceador de Carga)**
    * **Função:** Recebe requisições e as distribui eficientemente para um grupo de "serviços" (que podem ser outras instâncias de `LoadBalancerProxy` ou `ServiceProxy` no nível final).
    * **Comportamento:** Simula o roteamento de mensagens, a gerência de filas (com capacidade configurável) e o controle de quais serviços estão disponíveis para receber novas requisições.
    * **Configuração:** `config/loadbalancer1.properties` e `config/loadbalancer2.properties` definem suas portas, tamanho da fila, número de serviços que gerenciam e para onde os serviços devem rotear suas respostas.

3.  **`ServiceProxy` (Serviço)**
    * **Função:** Representa uma unidade de trabalho que processa uma requisição.
    * **Simulação:** Após receber uma mensagem, simula um tempo de processamento (baseado em um tempo de serviço e desvio padrão configuráveis) e, em seguida, envia a mensagem para o próximo destino na cadeia (que pode ser outro `LoadBalancerProxy` ou a `Source` novamente).

#### **Comunicação entre Componentes (Entrega 01):**

Nesta primeira etapa, a comunicação é **simulada em memória**. Isso significa que:

* **Sem Sockets Reais:** Os componentes **não** utilizam sockets TCP/IP ou comunicação de rede física.
* **Chamada Direta de Métodos:** A interação ocorre através da chamada direta de métodos (`receiving_messages`) entre as instâncias dos proxies, usando um registro global (`AbstractProxy._proxy_registry`) para "encontrar" a instância correta de destino pelo seu identificador (porta).
* **Propósito:** Esta abordagem simplificada permite validar a lógica do fluxo de mensagens, o cálculo de tempos e a interação entre os componentes de forma isolada e controlada, antes de introduzir a complexidade da rede real na próxima etapa.

#### **Fluxo de Requisições Típico na Entrega 01:**

1.  **`Source`** gera uma mensagem com um timestamp inicial.
2.  Essa mensagem é "enviada" para o **`LoadBalancerProxy 1`** (porta 2000).
3.  **`LoadBalancerProxy 1`** a coloca em sua fila e a distribui para um de seus `ServiceProxy`s internos.
4.  O `ServiceProxy` (gerenciado por LB1) simula o processamento e "envia" a mensagem para o **`LoadBalancerProxy 2`** (porta 3000).
5.  **`LoadBalancerProxy 2`** a distribui para um de seus `ServiceProxy`s internos.
6.  O `ServiceProxy` (gerenciado por LB2) simula o processamento e "envia" a mensagem de volta para o **`Source`** (porta 1000).
7.  A `Source` recebe a mensagem finalizada, calcula o tempo total de resposta e os T-values (tempos de transição entre os componentes) e os loga.

---

#### ** Como executar o sistema:**

No terminal, dentro da raiz do projeto execute o comando:

```
    python3 main.py
```

---

### Tecnologias Utilizadas

* **Python 3.12.3**: Linguagem de programação principal.
* **`threading`**: Módulo Python para lidar com concorrência e execução de componentes em threads separadas.
* **(Próxima Etapa) `socket`**: Módulo Python para comunicação de rede (será utilizado na Etapa 2 para sockets TCP/IP reais).
* **(Próxima Etapa) Docker**: Para conteinerização dos componentes na Etapa 2.

---

### 🤝 Autores

* [@NaraAndrad3](https://github.com/NaraAndrad3)

---