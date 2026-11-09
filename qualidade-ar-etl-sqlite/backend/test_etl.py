
"""Testes simples: executa `python -m unittest test_etl.py` na pasta backend."""

import io
import os
import tempfile
import unittest
from pathlib import Path
from csv_parser import extrair_transformar


# ============================================================
# 1. DEFINIÇÃO DOS DADOS DE TESTE
# ============================================================

# Define o cabeçalho de um ficheiro CSV utilizado para testar
# o funcionamento do processo ETL (Extract, Transform, Load).
#
# O cabeçalho contém os 19 campos existentes nos ficheiros
# originais dos sensores de qualidade do ar:
#
# - 4 campos temporais: início e fim em UTC e Europe/Lisbon;
# - 6 poluentes: NO2, O3, CO, SO2, PM1, PM10 e PM2P5
#   (na realidade são 7 parâmetros de poluição);
# - 3 parâmetros atmosféricos: pressão, humidade e temperatura;
# - 3 parâmetros do vento: direção, velocidade e rajada;
# - 2 coordenadas geográficas: latitude e longitude.
#
# Cada coluna mantém o nome e a unidade utilizados no CSV.
# O carácter \n representa o fim da linha do cabeçalho.
#
# Esta variável permite testar se o ETL consegue reconhecer
# os campos e converter os seus nomes para o formato interno.
CABECALHO = (
    'timestamp_init_UTC,timestamp_end_UTC,timestamp_init_Europe/Lisbon,'
    'timestamp_end_Europe/Lisbon,NO2(µg/m³),O3(µg/m³),CO(mg/m³),'
    'SO2(µg/m³),PM1(µg/m³),pressure(µg/m³),relativeHumidity(%),'
    'temperature(C),PM10(µg/m³),PM2P5(µg/m³),windDirection(degrees),'
    'windSpeed(m/s),windGust(m/s),latitude,longitude\n'
)


# Define uma linha de dados de exemplo para os testes.
#
# Esta linha simula uma leitura real de um sensor em Beja,
# correspondente ao período entre:
#
# 01/03/2025 00:00 UTC e 02/03/2025 00:00 UTC.
#
# O registo contém concentrações de poluentes, indicadores
# meteorológicos, características do vento e coordenadas.
#
# Alguns valores relevantes para as verificações são:
#
# CO       = 0.042 mg/m³
# PM2P5    = 8 µg/m³
# pressure = 984.5 (unidade indicada no CSV original)
#
# A utilização de valores conhecidos permite verificar
# posteriormente se a transformação realizada pelo ETL
# preserva corretamente a informação.
LINHA = (
    '2025-03-01T00:00:00.000Z,2025-03-02T00:00:00.000Z,'
    '2025-03-01T00:00:00.000+00:00,2025-03-02T00:00:00.000+00:00,'
    '19.5,30.5,0.042,2.6,8,984.5,78.7,13.41,18,8,4.886220851983609,'
    '1.2,3.6,38.0126,-7.85931\n'
)


# ============================================================
# 2. CLASSE DE TESTES UNITÁRIOS DO ETL
# ============================================================

# Cria uma classe destinada à execução de testes automáticos.
#
# A classe herda de unittest.TestCase, disponibilizando
# métodos de validação como assertEqual().
#
# O unittest identifica automaticamente os métodos
# cujo nome começa por "test_".
#
# Estes testes verificam especificamente o comportamento
# da função extrair_transformar(), existente em csv_parser.py.
#
# Não testam diretamente a inserção dos dados no SQLite.
class TestETL(unittest.TestCase):

    # --------------------------------------------------------
    # TESTE 1 — EXTRAÇÃO E TRANSFORMAÇÃO DE UMA LEITURA VÁLIDA
    # --------------------------------------------------------

    def test_exemplo(self):
        """
        Objetivo:
            Verificar se o ETL consegue processar corretamente
            um ficheiro CSV com uma leitura válida.

        O teste confirma:
            - A existência de uma leitura transformada;
            - A ausência de erros de validação;
            - A preservação dos valores de CO, PM2P5 e pressão;
            - A normalização do timestamp final em UTC.
        """

        # Junta o cabeçalho e a linha de exemplo para simular
        # o conteúdo completo de um pequeno ficheiro CSV.
        #
        # encode() converte o texto em bytes.
        #
        # io.BytesIO() cria um ficheiro binário em memória,
        # evitando a necessidade de criar um ficheiro físico.
        #
        # A função extrair_transformar() devolve dois resultados:
        # dados: lista de leituras transformadas com sucesso.
        # erros: lista de linhas rejeitadas e respetivos motivos.
        dados, erros = extrair_transformar(
            io.BytesIO((CABECALHO + LINHA).encode())
        )

        # Verifica se foi processada exatamente uma leitura.
        #
        # len(dados) devolve o número de registos válidos.
        #
        # O teste falha se a função rejeitar a leitura
        # ou produzir uma quantidade diferente de registos.
        self.assertEqual(len(dados), 1)

        # Confirma que nenhuma linha foi rejeitada.
        #
        # Uma lista vazia significa que não foram registados
        # erros durante a validação da leitura apresentada.
        self.assertEqual(erros, [])

        # Verifica o valor do monóxido de carbono (CO).
        #
        # O ETL deve converter o conteúdo textual "0.042"
        # para um valor numérico Python equivalente a 0.042.
        self.assertEqual(dados[0]['CO'], 0.042)

        # Verifica a concentração de partículas PM2.5.
        #
        # O índice [0] identifica a primeira leitura válida.
        # A chave 'PM2P5' identifica o respetivo poluente.
        #
        # Espera-se que o valor seja igual a 8.
        self.assertEqual(dados[0]['PM2P5'], 8)

        # Verifica o valor da pressão atmosférica.
        #
        # Confirma que o valor 984.5 foi corretamente extraído
        # e convertido para um número, sem ser modificado.
        self.assertEqual(dados[0]['pressure'], 984.5)

        # Verifica a normalização do timestamp final UTC.
        #
        # O CSV original contém:
        # 2025-03-02T00:00:00.000Z
        #
        # O ETL transforma esta representação em:
        # 2025-03-02T00:00:00.000+00:00
        #
        # Ambas representam o mesmo instante em UTC.
        #
        # Esta validação confirma que o timestamp foi
        # interpretado e normalizado corretamente.
        self.assertEqual(
            dados[0]['timestamp_end_UTC'],
            '2025-03-02T00:00:00.000+00:00'
        )

    # --------------------------------------------------------
    # TESTE 2 — DETEÇÃO DE INTERVALOS TEMPORAIS DUPLICADOS
    # --------------------------------------------------------

    def test_intervalo_duplicado(self):
        """
        Objetivo:
            Verificar se o ETL identifica leituras duplicadas
            dentro do mesmo ficheiro CSV.

        Cenário:
            São fornecidas duas linhas exatamente iguais,
            com os mesmos timestamps de início e fim.

        Resultado esperado:
            - Apenas uma leitura é aceite;
            - A segunda leitura é rejeitada como duplicada.

        Esta validação contribui para a qualidade dos dados
        antes do seu armazenamento na base de dados.
        """

        # Constrói um CSV de teste com:
        #
        # 1 cabeçalho;
        # 2 linhas de dados idênticas.
        #
        # O conteúdo é convertido em bytes e colocado
        # num ficheiro virtual através de io.BytesIO().
        #
        # A função extrair_transformar() irá analisar
        # as duas linhas e verificar a duplicação do intervalo.
        dados, erros = extrair_transformar(
            io.BytesIO((CABECALHO + LINHA + LINHA).encode())
        )

        # Confirma que apenas um registo foi aceite.
        #
        # Se o ETL aceitar as duas linhas, este teste falha,
        # porque os intervalos temporais são iguais.
        self.assertEqual(len(dados), 1)

        # Confirma que foi registada uma linha rejeitada.
        #
        # O ETL identifica a segunda ocorrência do intervalo
        # e adiciona a rejeição à lista de erros.
        #
        # Este teste verifica a quantidade de rejeições,
        # não o texto específico do motivo.
        self.assertEqual(len(erros), 1)


# ============================================================
# 3. EXECUÇÃO DOS TESTES
# ============================================================

# Verifica se o ficheiro está a ser executado diretamente.
#
# Quando o test_etl.py é executado pelo Python,
# a variável __name__ assume o valor '__main__'.
#
# Nesse caso, unittest.main() procura e executa
# automaticamente os métodos de teste da classe TestETL.
#
# Se o ficheiro for importado por outro módulo,
# este bloco não é executado automaticamente.
if __name__ == '__main__':
    unittest.main()
