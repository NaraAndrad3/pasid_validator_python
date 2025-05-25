# main.py

from src.tests.validation import local_test_service


if __name__ == "__main__":
   """"
    Executa o serviço de teste local para validação do PASID. O experimento é realizado de fato na classe local_test_services.
    Essa classe lê os arquivos de propriedades e executa o serviço de teste local.
   """

local_test_service.execute_stage()

    
   