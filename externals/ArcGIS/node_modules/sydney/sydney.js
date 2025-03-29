// Sydney
// ======
//
// [ ![Codeship Status for xaviervia/sydney](https://codeship.com/projects/317ce050-9903-0132-893b-365d53813970/status?branch=master)](https://codeship.com/projects/63545) [![Code Climate](https://codeclimate.com/github/xaviervia/sydney/badges/gpa.svg)](https://codeclimate.com/github/xaviervia/sydney) [![Test Coverage](https://codeclimate.com/github/xaviervia/sydney/badges/coverage.svg)](https://codeclimate.com/github/xaviervia/sydney/coverage)
//
// Event Subscription/Venue library. Whole new approach:
//
// - Asynchronous emission only. Synchronous programming is over.
// - The venue is a middleware. Propagation in the venue is mediated by
//   the main callback.
// - Subscribers are venues too. Broadcasting back into the source venue is
//   done by adding the source venue as a subscriber to its own subscribers
//   (this is called `linking`).
//
// The way events are treated is completely different. You can think of them
// as full requests, with headers and payload:
//
// - There is no difference between the event and the arguments sent to the
//   event. Events are assumed to be complex objects.
// - Optional `endpoint`s allow venues to check whether they are interested
//   in an event or not. This allows venues to link to each other promiscuously
//   and achieve very complex topologies in a scalable manner.
//
// > Usage documentation is pending
//
// Installation
// ------------
//
// ```shell
// npm install --save sydney
// ```
//

"use strict";

(function (name, definition) {

  //! AMD
  if (typeof define === 'function')
    define(definition)

  //! CommonJS
  else if (typeof module !== 'undefined' && module.exports)
    module.exports = definition()

  //! Browser
  else
    window[name] = definition()

})('Sydney', function () {
  // Methods
  // -------
  //
  // ### new( [endpoint] [, callback] )
  //
  // Creates a new Sydney venue. If only a `Function` is provided, it is used
  // as the `callback`. If only an `Object` of any other kind is provided,
  // it is used as the `endpoint`. If two arguments are provided, the first
  // is used as the `endpoint` and the second as the `callback`.
  //
  // > Note that `new` is completely optional. Calling `Sydney` as a function
  // > directly will have the same effect.
  //
  // #### Arguments
  //
  // - _optional_ `Object` endpoint
  // - _optional_ `Function` callback
  //
  // #### Returns
  //
  // - `Sydney` this
  //
  var Sydney = function (first, second) {
    if (!(this instanceof Sydney)) return new Sydney(first, second)

    if (second) {
      this.endpoint = first
      this.callback = second
    }

    else if (first) {
      if (first instanceof Function)
        this.callback = first

      else
        this.endpoint = first
    }
  }

  Sydney.testIfNextTickSupported = function () {
    try {
      if (global.process.nextTick instanceof Function)
        Sydney.nextTickSupported = true
      else
        Sydney.nextTickSupported = false
    }

    catch (e) { Sydney.nextTickSupported = false }
  }

  // ### Sydney.amplify( vanillaSubscriber )
  //
  // Adds `Sydney.prototype` methods as mixin to the `vanillaSubscriber`.
  //
  Sydney.amplify = function (vanillaSubscriber) {
    if (vanillaSubscriber.add === undefined)
      vanillaSubscriber.add = Sydney.prototype.add

    if (vanillaSubscriber.broadcast === undefined)
      vanillaSubscriber.broadcast = Sydney.prototype.broadcast

    if (vanillaSubscriber.link === undefined)
      vanillaSubscriber.link = Sydney.prototype.link

    if (vanillaSubscriber.remove === undefined)
      vanillaSubscriber.remove = Sydney.prototype.remove

    if (vanillaSubscriber.send === undefined)
      vanillaSubscriber.send = Sydney.prototype.send

    if (vanillaSubscriber.unlink === undefined)
      vanillaSubscriber.unlink = Sydney.prototype.unlink
  }

  // ### send( event )
  //
  // If the venue has an `endpoint`, it calls `match` with the `event` and
  // only calls the `callback` if the return value is `true`. If there is no
  // `endpoint` it always calls the `callback`. The callback is called with
  // the `event` as the first argument and the venue (`this`) as the second
  // argument.
  //
  // If there is no `callback`, the event is broadcasted to the subscribers
  // instead. That is done by calling `broadcast` with the `event` as
  // argument.
  //
  // #### Arguments
  //
  // - `Object` event
  //
  // #### Returns
  //
  // - `Sydney` this
  //
  Sydney.prototype.send = function (event) {
    var callback;

    if (this.callback)
      callback = function () { this.callback(event, this) }.bind(this)

    else callback = function () { this.broadcast(event) }.bind(this)

    if (this.endpoint && ! this.endpoint.match(event)) return this

    if (Sydney.nextTickSupported === undefined) Sydney.testIfNextTickSupported()

    if (Sydney.nextTickSupported) process.nextTick(callback)
    else  setTimeout(callback, 0)

    return this
  }

  // ### broadcast( event )
  //
  // Calls `send` with the provided `event` in all the subscribers.
  //
  // #### Arguments
  //
  // - `Object` event
  //
  // #### Returns
  //
  // - `Sydney` this
  //
  Sydney.prototype.broadcast = function (event) {
    (this.subscribers = this.subscribers || []).forEach(function (subscriber) {
      subscriber.send(event)
    })

    return this
  }

  // ### add( subscriber )
  //
  // If the `subscriber` is a `Sydney` venue, it just adds it as a
  // subscriber in the current venue.
  //
  // If the `subscriber` is not a `Sydney` module, it adds all of `Sydney`
  // methods to the `subscriber`. It doesn't override properties already
  // existing on the `subscriber`.
  //
  // #### Returns
  //
  // - `Sydney` this
  //
  Sydney.prototype.add = function (subscriber) {
    this.subscribers = this.subscribers || []

    if (!(subscriber instanceof Sydney))
      Sydney.amplify(subscriber)

    this.subscribers.push(subscriber)

    return this
  }

  // ### remove( subscriber )
  //
  // Removes the `subscriber` from the venue.
  //
  // #### Arguments
  //
  // - `Object` subscriber
  //
  // #### Returns
  //
  // - `Sydney` this
  //
  Sydney.prototype.remove = function (targetSubscriber) {
    if ( ! this.subscribers) return this

    this.subscribers = this.subscribers.filter(function (subscriber) {
      return subscriber !== targetSubscriber
    })

    return this
  }

  // ### link( subscriber )
  //
  // If the `subscriber` is a `Sydney` venue, it just adds it as a
  // subscriber in the current venue. Then adds the venue back into the
  // subscriber.
  //
  // If the `subscriber` is not a `Sydney` module, it adds all of `Sydney`
  // methods to the `subscriber`. It doesn't override properties already
  // existing on the `subscriber`.
  //
  // #### Returns
  //
  // - `Sydney` this
  //
  Sydney.prototype.link = function (subscriber) {
    if (!(subscriber instanceof Sydney))
      Sydney.amplify(subscriber)

    this.add(subscriber)

    subscriber.add(this)

    return this
  }

  // ### unlink( subscriber )
  //
  // Removes the `subscriber` from the venue and removes the venue from
  // the `subscriber`.
  //
  // #### Arguments
  //
  // - `Object` subscriber
  //
  // #### Returns
  //
  // - `Sydney` this
  //
  Sydney.prototype.unlink = function (subscriber) {
    subscriber.remove(this)

    this.remove(subscriber)

    return this
  }


  return Sydney

})
//
// Testing
// -------
//
// ```
// git clone git://github.com/xaviervia/sydney
// cd sydney
// npm install
// make test
// ```
//
// License
// -------
//
// Copyright 2015 Xavier Via
//
// ISC license.
//
// See [LICENSE](LICENSE) attached.
