
"use strict"


var example = require("washington")
var Sydney  = require("../sydney")


example("#link: add as subscriber", function () {
  var mother    = new Sydney
  var daughter  = new Sydney

  mother.link(daughter)

  return mother.subscribers[0] === daughter
})


example("#link: subscribe back", function () {
  var mother    = new Sydney
  var daughter  = new Sydney

  mother.link(daughter)

  return daughter.subscribers[0] === mother
})


example("#link: add @vanilla module as subscriber", function () {
  var mother    = new Sydney
  var daughter  = {}

  mother.link(daughter)

  return mother.subscribers[0] === daughter
})


example("#link: @vanilla add venue back", function () {
  var mother    = new Sydney
  var daughter  = {}

  mother.link(daughter)

  return daughter.subscribers[0] === mother
})


example("#link: amplify @vanilla module with #add", function () {
  var venue       = new Sydney
  var subscriber  = {}

  venue.link(subscriber)

  return subscriber.add === Sydney.prototype.add
})


example("#link: amplify @vanilla module with #broadcast", function () {
  var venue       = new Sydney
  var subscriber  = {}

  venue.link(subscriber)

  return subscriber.broadcast === Sydney.prototype.broadcast
})


example("#link: amplify @vanilla module with #link", function () {
  var venue       = new Sydney
  var subscriber  = {}

  venue.link(subscriber)

  return subscriber.link === Sydney.prototype.link
})


example("#link: amplify @vanilla module with #remove", function () {
  var venue       = new Sydney
  var subscriber  = {}

  venue.link(subscriber)

  return subscriber.remove === Sydney.prototype.remove
})


example("#link: amplify @vanilla module with #send", function () {
  var venue       = new Sydney
  var subscriber  = {}

  venue.link(subscriber)

  return subscriber.send === Sydney.prototype.send
})


example("#link: amplify @vanilla module with #unlink", function () {
  var venue       = new Sydney
  var subscriber  = {}

  venue.link(subscriber)

  return subscriber.unlink === Sydney.prototype.unlink
})


example("#link: don't replace @vanilla #add property", function () {
  var venue       = new Sydney
  var property    = function () {}
  var subscriber  = {
    add: property
  }

  venue.link(subscriber)

  return subscriber.add === property
})


example("#link: don't replace @vanilla #broadcast property", function () {
  var venue       = new Sydney
  var property    = { name: "original" }
  var subscriber  = {
    broadcast: property
  }

  venue.link(subscriber)

  return subscriber.broadcast === property
})


example("#link: don't replace @vanilla #link property", function () {
  var venue       = new Sydney
  var property    = { name: "original" }
  var subscriber  = {
    link: property
  }

  venue.link(subscriber)

  return subscriber.link === property
})


example("#link: don't replace @vanilla #remove property", function () {
  var venue       = new Sydney
  var property    = { name: "original" }
  var subscriber  = {
    remove: property
  }

  venue.link(subscriber)

  return subscriber.remove === property
})


example("#link: don't replace @vanilla #send property", function () {
  var venue       = new Sydney
  var property    = { name: "original" }
  var subscriber  = {
    send: property
  }

  venue.link(subscriber)

  return subscriber.send === property
})


example("#link: don't replace @vanilla #unlink property", function () {
  var venue       = new Sydney
  var property    = { name: "original" }
  var subscriber  = {
    unlink: property
  }

  venue.link(subscriber)

  return subscriber.unlink === property
})


example("#link: don't replace @vanilla #subscribers property", function () {
  var venue       = new Sydney
  var subscribers = []
  var subscriber  = {
    subscribers: subscribers
  }

  venue.link(subscriber)

  return subscriber.subscribers === subscribers
})


example("#link: chainable", function () {
  var mother = new Sydney

  return mother.link(function () {}) === mother
})
