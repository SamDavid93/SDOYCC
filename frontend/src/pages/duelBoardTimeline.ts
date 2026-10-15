import type { DuelEvent } from './DuelAnimations'
import type { Side } from './DuelWorkerTable'

type Snapshot = { through: number; sides: Side[] }

/** Keep field and piles on the same completed event boundary as playback. */
export class DuelBoardTimeline {
  private game: number | null = null
  private snapshots: Snapshot[] = []

  record(game: number, events: DuelEvent[], sides: Side[]) {
    // The result banner follows the final move; it must not hold defeated
    // monsters on the field throughout the victory animation.
    const through = Math.max(0, ...events.filter(event => event.kind !== 'win').map(event => event.id))
    if (this.game !== game) {
      this.game = game
      this.snapshots = []
    }
    const previous = this.snapshots.at(-1)
    // Heartbeats and metadata refreshes are the same engine boundary.
    if (previous?.through === through) this.snapshots[this.snapshots.length - 1] = { through, sides }
    else this.snapshots.push({ through, sides })
  }

  visible(game: number, through: number): Side[] | undefined {
    if (this.game !== game) return undefined
    let index = this.completedIndex(through)
    // The first snapshot is the connection/reconnection baseline, not a replay.
    if (index < 0) index = 0
    return this.snapshots[index]?.sides
  }

  complete(game: number, through: number) {
    if (this.game !== game) return
    const index = this.completedIndex(through)
    if (index > 0) this.snapshots.splice(0, index)
  }

  private completedIndex(through: number) {
    for (let index = this.snapshots.length - 1; index >= 0; index--) {
      if (this.snapshots[index].through <= through) return index
    }
    return -1
  }
}
