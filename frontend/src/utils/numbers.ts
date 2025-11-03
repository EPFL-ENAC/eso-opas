// Function to convert decimal degrees to DMS (Degrees, Minutes, Seconds)
export function toDMS(deg: number) {
  const d = Math.floor(deg)
  const minFloat = (deg - d) * 60
  const m = Math.floor(minFloat)
  const secFloat = (minFloat - m) * 60
  const s = Math.round(secFloat)

  return `${d}° ${m}' ${s}"`
}

// Function to convert decimal coordinates to a user-friendly format (DMS + N/S/E/W)
export function formatCoordinates(lat: number, lon: number) {
  const latDirection = lat >= 0 ? 'N' : 'S'
  const lonDirection = lon >= 0 ? 'E' : 'W'

  const latDMS = toDMS(Math.abs(lat)) // Get absolute value of latitude
  const lonDMS = toDMS(Math.abs(lon)) // Get absolute value of longitude

  return `${latDMS} ${latDirection}, ${lonDMS} ${lonDirection}`
}

export function toMaxDecimals(x: number | null, n: number): number | null {
  if (x === null) {
    return null
  }
  return +x.toFixed(n)
}
