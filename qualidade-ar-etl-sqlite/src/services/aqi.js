
/*
 * Cálculo demonstrativo do AQI a partir de PM2.5.
 *
 * Utiliza a concentração média das últimas 24 horas.
 * O AQI é um índice sem unidade, diferente de µg/m³.
 *
 * As faixas utilizadas são demonstrativas e devem ser
 * verificadas antes de utilizar o índice como valor oficial.
 */

// Intervalos de concentração e respetivas categorias AQI
const faixas = [
  [0, 9, 0, 50],
  [9.1, 35.4, 51, 100],
  [35.5, 55.4, 101, 150],
  [55.5, 125.4, 151, 200],
  [125.5, 225.4, 201, 300],
  [225.5, 325.4, 301, 500]
]

// Converte a concentração média de PM2.5 num valor AQI.
export function calcularAqiPm25(media24h) {
  if (
    media24h == null ||
    !Number.isFinite(Number(media24h)) ||
    Number(media24h) < 0
  ) {
    return null
  }

  // A concentração é truncada a uma casa decimal.
  const c = Math.floor(Number(media24h) * 10) / 10

  // Identifica a faixa de concentração.
  const faixa = faixas.find(
    ([min, max]) => c >= min && c <= max
  )

  if (!faixa) return null

  const [cMin, cMax, iMin, iMax] = faixa

  // Interpolação linear para calcular o índice.
  return Math.round(
    ((iMax - iMin) / (cMax - cMin)) *
    (c - cMin) + iMin
  )
}

/*
 * Calcula o AQI de um sensor numa janela de 24 horas.
 *
 * O ETL guarda os timestamps de início e fim em UTC.
 * Cada leitura representa uma média do respetivo intervalo.
 *
 * Exemplo:
 * - 1 registo com duração de 24 horas
 * - 24 registos com duração de 1 hora
 *
 * Ambos podem produzir uma média válida de 24 horas.
 *
 * Não inventamos valores para períodos sem leituras.
 */
export function calcularAqiIntervalo(
  leituras,
  sensorId,
  leituraReferencia
) {
  // Termina a janela na data final da leitura selecionada.
  const fim = Date.parse(
    leituraReferencia?.timestamp_end_UTC
  )

  if (!Number.isFinite(fim)) return null

  // Início da janela: 24 horas antes.
  const inicio = fim - 24 * 60 * 60 * 1000

  // Seleciona as leituras do sensor com PM2.5 válido.
  const intervalos = leituras
    .filter(
      l =>
        Number(l.sensor_id) === Number(sensorId) &&
        l.PM2P5 != null
    )
    .map(l => ({
      inicio: Date.parse(l.timestamp_init_UTC),
      fim: Date.parse(l.timestamp_end_UTC),
      valor: Number(l.PM2P5)
    }))
    .filter(l =>
      Number.isFinite(l.inicio) &&
      Number.isFinite(l.fim) &&
      l.fim > l.inicio &&
      l.fim > inicio &&
      l.inicio < fim &&
      Number.isFinite(l.valor) &&
      l.valor >= 0
    )
    .sort((a, b) => a.inicio - b.inicio)

  let cursor = inicio
  let somaPonderada = 0

  // Verifica a continuidade dos intervalos.
  for (const intervalo of intervalos) {
    const de = Math.max(intervalo.inicio, inicio)
    const ate = Math.min(intervalo.fim, fim)

    // Se existir uma lacuna ou sobreposição, não calcula.
    if (de !== cursor || ate <= de) {
      return null
    }

    // A concentração é ponderada pela duração.
    somaPonderada += intervalo.valor * (ate - de)
    cursor = ate
  }

  // Só calcula se as 24 horas estiverem completas.
  if (cursor !== fim) return null

  const media24h = somaPonderada / (fim - inicio)

  return calcularAqiPm25(media24h)
}
