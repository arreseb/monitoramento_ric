# Arquivo de execução local (wrapper)
# Importa o app e inicializa o banco a partir do arquivo principal.
# Mantemos o código da aplicação em `servidor_web_e_api.py` e usamos este
# wrapper para executar localmente (útil para Docker e testes locais).

from servidor_web_e_api import inicializar_banco, app

if __name__ == '__main__':
    # Garante que a tabela exista antes de iniciar o servidor
    inicializar_banco()
    # Executa o servidor Flask na porta 5000 (igual ao original)
    app.run(host='0.0.0.0', port=5000, debug=True)
