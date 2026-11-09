import assert from 'node:assert/strict'
import test from 'node:test'
import { topPercent } from '../src/utils/percentile.js'

test('topPercent converts percentiles to the intuitive top percentage', () => {
  assert.equal(topPercent(100), 0)
  assert.equal(topPercent(97.56), 2.44)
  assert.equal(topPercent(50), 50)
  assert.equal(topPercent(0), 100)
})
