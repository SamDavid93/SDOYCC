/** Keep engine indexes and order; double-click confirms only a complete legal-size selection. */
export function includeChoice(selection: number[], index: number, maximum: number) {
  if (maximum === 1) return [index]
  if (selection.includes(index)) return selection
  return selection.length < maximum ? [...selection, index] : selection
}

export function selectionComplete(selection: number[], minimum: number, maximum: number) {
  return selection.length >= minimum && selection.length <= maximum
}
