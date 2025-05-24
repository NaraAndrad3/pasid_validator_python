# Pasid Validator Python


### Estrutura do projeto
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