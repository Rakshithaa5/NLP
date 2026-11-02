import test from 'node:test'
import assert from 'node:assert/strict'
import { actionNoteKey, readActionNote, saveActionNote } from './notes.js'

test('personal notes can be added, read, edited, and deleted without changing extraction', () => {
  const values = new Map()
  const storage = {getItem: key => values.get(key) ?? null, setItem: (key,value) => values.set(key,value), removeItem: key => values.delete(key)}
  const item = {task:'Send notes', owner:'Alex', deadline:'Friday', evidence:'Send notes by Friday', segment_ids:[0]}
  const before = JSON.stringify(item)
  const key = actionNoteKey('meeting-a', item)
  assert.equal(readActionNote(storage,key), '')
  saveActionNote(storage,key,'  My reminder  ')
  assert.equal(readActionNote(storage,key),'My reminder')
  saveActionNote(storage,key,'Updated reminder')
  assert.equal(readActionNote(storage,key),'Updated reminder')
  assert.equal(readActionNote(storage,actionNoteKey('meeting-b',item)), '')
  assert.notEqual(key,actionNoteKey('meeting-a',{...item,segment_ids:[1]}))
  saveActionNote(storage,key,'')
  assert.equal(readActionNote(storage,key),'')
  assert.equal(values.size,0)
  assert.equal(JSON.stringify(item),before)
})

test('storage failure is surfaced instead of reporting a successful save', () => {
  assert.throws(() => saveActionNote({setItem() {throw new Error('quota')}},'key','note'), /quota/)
})
