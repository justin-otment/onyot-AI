
"use strict"


var example = require("washington")
var Sydney  = require("../sydney")


example("#broadcast: send to the subscriber", function (check) {
  var venue = new Sydney
  var event = { name: "event" }

  venue.add({
    callback: function (e) { check(e, event) }
  })

  venue.broadcast(event)
})


example("#broadcast: chainable", function () {
  var venue = new Sydney
  var event = { name: "event" }

  venue.add(function () {})

  return venue.broadcast(event) === venue
})


example("#broadcast: @no-subscribers won't fail", function () {
  new Sydney().broadcast()
})
