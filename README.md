# Pasid Validator Python

Escrito originalmente em Java, O PASID-VALIDATOR serve para montar um sistema distribuído cliente-servidor(es) e capturar os tempos de cada etapa do processamento. Este projeto reescreve o PASID-VALIDOR na linguagem python, como parte da proposta do trabalho final da disciplina de Sistemas Distribuidos. O projeto é dividido em duas etapas:

 <ul>
    <li> A primeira etapa consiste na apenas na reescrita do projeto na linguagem de programação python.</li>
    <li> A segunda etapa consistem em executar experimentos usando os componentes em docker containers (1 SOURCE, 2 LOAD BALANCERS).</li>
    <ul>

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




## Tecnologias Utilizadas

    Python 3.12.3
    Sockets
    

## Autores
@NaraAndrad3