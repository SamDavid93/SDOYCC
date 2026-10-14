// Animation rendering only: keep the downloaded originals and catalogue unchanged.
const cache = new Map<string, Promise<string>>()

export function transparentPackCover(url: string): Promise<string> {
  const existing = cache.get(url)
  if (existing) return existing
  const result = new Promise<string>((resolve, reject) => {
    const image = new Image()
    image.onload = () => {
      try {
        const canvas = document.createElement('canvas')
        const width = canvas.width = image.naturalWidth
        const height = canvas.height = image.naturalHeight
        const context = canvas.getContext('2d', { willReadFrequently: true })!
        context.drawImage(image, 0, 0)
        const pixels = context.getImageData(0, 0, width, height)
        const data = pixels.data
        const visited = new Uint8Array(width * height)
        const queue = new Uint32Array(width * height)
        let head = 0, tail = 0
        const add = (index: number) => {
          if (visited[index]) return
          visited[index] = 1
          const offset = index * 4
          const low = Math.min(data[offset], data[offset + 1], data[offset + 2])
          const high = Math.max(data[offset], data[offset + 1], data[offset + 2])
          let background = low >= 222 && high - low <= 26
          if (!background && low >= 170 && high - low <= 26) {
            // Studio shadows form smooth neutral gradients. Preserve sharp
            // packaging edges instead of flooding into silver foil or print.
            const x = index % width
            const neighbors = [x ? index - 1 : index, x < width - 1 ? index + 1 : index,
              index >= width ? index - width : index, index < width * (height - 1) ? index + width : index]
            background = neighbors.every(neighbor => [0, 1, 2].every(channel => Math.abs(data[offset + channel] - data[neighbor * 4 + channel]) <= 24))
          }
          if (data[offset + 3] === 0 || background) queue[tail++] = index
        }
        for (let x = 0; x < width; x++) { add(x); add((height - 1) * width + x) }
        for (let y = 0; y < height; y++) { add(y * width); add(y * width + width - 1) }
        while (head < tail) {
          const index = queue[head++]
          data[index * 4 + 3] = 0
          const x = index % width
          if (x > 0) add(index - 1)
          if (x < width - 1) add(index + 1)
          if (index >= width) add(index - width)
          if (index < width * (height - 1)) add(index + width)
        }
        // Only the edge-connected studio backdrop disappears. Enclosed white
        // print, logos and bright artwork retain their original pixels.
        context.putImageData(pixels, 0, 0)
        resolve(canvas.toDataURL('image/png'))
      } catch (error) { reject(error) }
    }
    image.onerror = () => reject(new Error('Packcover konnte nicht geladen werden'))
    image.src = url
  })
  cache.set(url, result)
  if (cache.size > 12) cache.delete(cache.keys().next().value!)
  result.catch(() => cache.delete(url))
  return result
}
