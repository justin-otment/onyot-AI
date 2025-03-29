
"use strict"


var example = require("washington")
var Sydney  = require("../sydney")


example("#new: takes a callback", function () {
  var callback = function () {}

  return new Sydney(callback).callback === callback
})


example("#new: takes an endpoint if has `match`", function () {
  var endpoint = { match: function () {} }

  return new Sydney(endpoint).endpoint === endpoint
})


example("#new: @endpoint endpoint is first argument", function () {
  var endpoint = { match: function () {} }
  var callback = function () {}
  var venue = new Sydney(endpoint, callback)

  return venue.endpoint === endpoint
})


example("#new: @endpoint callback is second argument", function () {
  var endpoint = { match: function () {} }
  var callback = function () {}
  var venue = new Sydney(endpoint, callback)

  return venue.callback === callback
})


example("#Sydney: no need for new", function () {
  return Sydney() instanceof Sydney
})
