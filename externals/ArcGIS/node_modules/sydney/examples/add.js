
"use strict"


var example = require("washington")
var Sydney  = require("../sydney")


example("#add: add the Sydney venue as subscriber", function () {
  var venue       = new Sydney
  var subscriber  = new Sydney

  venue.add(subscriber)

  return venue.subscribers[0] === subscriber
})


example("#add: add @vanilla module as subscriber", function () {
  var venue       = new Sydney
  var subscriber  = {}

  venue.add(subscriber)

  return venue.subscribers[0] === subscriber
})


example("#add: amplify @vanilla module with #add", function () {
  var venue       = new Sydney
  var subscriber  = {}

  venue.add(subscriber)

  return subscriber.add === Sydney.prototype.add
})


example("#add: amplify @vanilla module with #broadcast", function () {
  var venue       = new Sydney
  var subscriber  = {}

  venue.add(subscriber)

  return subscriber.broadcast === Sydney.prototype.broadcast
})


example("#add: amplify @vanilla module with #link", function () {
  var venue       = new Sydney
  var subscriber  = {}

  venue.add(subscriber)

  return subscriber.link === Sydney.prototype.link
})


example("#add: amplify @vanilla module with #remove", function () {
  var venue       = new Sydney
  var subscriber  = {}

  venue.add(subscriber)

  return subscriber.remove === Sydney.prototype.remove
})


example("#add: amplify @vanilla module with #send", function () {
  var venue       = new Sydney
  var subscriber  = {}

  venue.add(subscriber)

  return subscriber.send === Sydney.prototype.send
})


example("#add: amplify @vanilla module with #unlink", function () {
  var venue       = new Sydney
  var subscriber  = {}

  venue.add(subscriber)

  return subscriber.unlink === Sydney.prototype.unlink
})


example("#add: don't replace @vanilla #add property", function () {
  var venue       = new Sydney
  var property    = { name: "original" }
  var subscriber  = {
    add: property
  }

  venue.add(subscriber)

  return subscriber.add === property
})


example("#add: don't replace @vanilla #broadcast property", function () {
  var venue       = new Sydney
  var property    = { name: "original" }
  var subscriber  = {
    broadcast: property
  }

  venue.add(subscriber)

  return subscriber.broadcast === property
})


example("#add: don't replace @vanilla #link property", function () {
  var venue       = new Sydney
  var property    = { name: "original" }
  var subscriber  = {
    link: property
  }

  venue.add(subscriber)

  return subscriber.link === property
})


example("#add: don't replace @vanilla #remove property", function () {
  var venue       = new Sydney
  var property    = { name: "original" }
  var subscriber  = {
    remove: property
  }

  venue.add(subscriber)

  return subscriber.remove === property
})


example("#add: don't replace @vanilla #send property", function () {
  var venue       = new Sydney
  var property    = { name: "original" }
  var subscriber  = {
    send: property
  }

  venue.add(subscriber)

  return subscriber.send === property
})


example("#add: don't replace @vanilla #unlink property", function () {
  var venue       = new Sydney
  var property    = { name: "original" }
  var subscriber  = {
    unlink: property
  }

  venue.add(subscriber)

  return subscriber.unlink === property
})


example("#add: don't replace @vanilla #subscribers property", function () {
  var venue       = new Sydney
  var subscribers = []
  var subscriber  = {
    subscribers: subscribers
  }

  venue.add(subscriber)

  return subscriber.subscribers === subscribers
})


example("#add: chainable", function () {
  var venue       = new Sydney
  var subscriber  = function () {}

  return venue.add(subscriber) === venue
})
