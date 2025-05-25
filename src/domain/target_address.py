class TargetAddress:
    '''Classe  para armazenar IP e porta dos componentes do sistema.'''
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port

    def get_ip(self):
        return self.ip

    def get_port(self):
        return self.port

    def __str__(self):
        return f"TargetAddress(ip='{self.ip}', port={self.port})"







# print(TargetAddress.__doc__)