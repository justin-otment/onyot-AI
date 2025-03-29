
"use strict"


var example = require("washington")
var Sydney  = require("../sydney")


example("#unlink: remove from venue", function () {
  var mother    = new Sydney
  var daughter  = new Sydney

  mother.link(daughter)

  mother.unlink(daughter)

  return mother.subscribers.length === 0
})


example("#unlink: remove venue from subscriber", function () {
  var mother    = new Sydney
  var daughter  = new Sydney

  mother.link(daughter)

  mother.unlink(daughter)

  return daughter.subscribers.length === 0
})


example("#unlink: remove the @vanilla subscriber", function () {
  var mother    = new Sydney
  var daughter  = {}

  mother.link(daughter)

  mother.unlink(daughter)

  return daughter.subscribers.length === 0
})


example("#unlink: @vanilla remove the venue from the subscriber", function () {
  var mother    = new Sydney
  var daughter  = {}

  mother.link(daughter)

  mother.unlink(daughter)

  return mother.subscribers.length === 0
})


example("#unlink: chainable", function () {
  var mother    = new Sydney
  var daughter  = new Sydney

  mother.link(daughter)

  return mother.unlink(daughter) === mother
})


example("#unlink: @no-subscribers won't fail", function () {
  new Sydney().unlink(new Sydney)
})
