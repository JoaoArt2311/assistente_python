# Assistente de Suporte TI

Automação em Python para o trabalho diário de suporte em computadores Windows.

## O que esta versão faz

### Inventário da máquina

- Coleta computador, usuário, fabricante, modelo e número de série.
- Mostra versão e arquitetura do Windows.
- Coleta processador, memória RAM e discos.
- Lista IPv4, gateway, DNS e endereço MAC das redes ativas.
- Lista as impressoras configuradas.
- Salva o relatório em `.txt` e `.json`.

### Impressoras

- Lista impressoras e drivers instalados.
- Adiciona impressora compartilhada, por exemplo `\\SERVIDOR\\Financeiro`.
- Cria porta TCP/IP e adiciona uma impressora por IPv4.
- Instala um pacote de driver a partir de um arquivo `.INF`.
- Define a impressora padrão.
- Imprime uma página de teste.
- Remove uma impressora após confirmação.
- Reinicia o serviço de impressão após confirmação.

## Requisitos

- Windows 10 ou Windows 11.
- Python 3.10 ou mais recente para executar o código-fonte.
- Algumas ações de impressora precisam de uma conta com permissão de administrador.
- Para adicionar por IP, o driver correto precisa estar instalado. Use o botão **Instalar driver (.INF)** antes, quando necessário.

## Como executar

1. Instale o Python 3.10 ou mais recente. O iniciador reconhece os comandos `py` e `python`, além das pastas padrão do Windows.
2. Extraia todos os arquivos deste projeto.
3. Clique duas vezes em `executar.bat`.

Também é possível abrir o Prompt de Comando na pasta e executar:

```bat
py -3 app.py
```

Se o comando `py` não estiver disponível, tente `python app.py`. O arquivo `executar.bat` não depende mais somente da opção **Add Python to PATH**.

## Como gerar um arquivo EXE

1. Clique com o botão direito em `gerar_exe.bat` e selecione **Executar como administrador**.
2. Aguarde a conclusão.
3. O programa será criado em `dist\AssistenteTI.exe`.

O EXE solicitará permissão de administrador ao ser aberto. Isso permite instalar drivers, criar portas TCP/IP e reiniciar o serviço de impressão.

## Observações importantes

- A ferramenta utiliza apenas recursos nativos do Windows: PowerShell, CIM/WMI, PrintManagement e `pnputil`.
- Nenhuma informação da máquina é enviada para a internet.
- O botão de inventário é somente leitura e não altera configurações.
- Antes de instalar um driver, obtenha o pacote no site oficial do fabricante da impressora.
- Em ambientes corporativos, teste primeiro em uma máquina de homologação.

## Estrutura do projeto

- `app.py`: aplicação e interface gráfica.
- `executar.bat`: inicia o projeto pelo Python.
- `localizar_python.bat`: localiza o Python pelo lançador ou pelas pastas padrão do Windows.
- `gerar_exe.bat`: instala o empacotador e gera o EXE.
- `requirements-build.txt`: dependência usada somente para gerar o EXE.
