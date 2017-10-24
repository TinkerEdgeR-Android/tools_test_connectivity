#!/usr/bin/python3.4
#
#   Copyright 2017 - The Android Open Source Project
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import queue
import time

from acts import asserts
from acts.test_utils.wifi.aware import aware_const as aconsts
from acts.test_utils.wifi.aware import aware_test_utils as autils
from acts.test_utils.wifi.aware.AwareBaseTest import AwareBaseTest
from acts.test_utils.wifi.rtt import rtt_const as rconsts
from acts.test_utils.wifi.rtt import rtt_test_utils as rutils
from acts.test_utils.wifi.rtt.RttBaseTest import RttBaseTest


class RangeAwareTest(AwareBaseTest, RttBaseTest):
  """Test class for RTT ranging to Wi-Fi Aware peers"""
  SERVICE_NAME = "GoogleTestServiceXY"

  # Number of RTT iterations
  NUM_ITER = 10

  # Allowed margin of distance measurements (in %)
  DISTANCE_MARGIN = 10

  # Maximum expected RSSI
  MAX_EXPECTED_RSSI = 200

  # Time gap (in seconds) between iterations
  TIME_BETWEEN_ITERATIONS = 0

  # Time gap (in seconds) when switching between Initiator and Responder
  TIME_BETWEEN_ROLES = 0

  def __init__(self, controllers):
    AwareBaseTest.__init__(self, controllers)
    RttBaseTest.__init__(self, controllers)

  def setup_test(self):
    """Manual setup here due to multiple inheritance: explicitly execute the
    setup method from both parents."""
    AwareBaseTest.setup_test(self)
    RttBaseTest.setup_test(self)

  def teardown_test(self):
    """Manual teardown here due to multiple inheritance: explicitly execute the
    teardown method from both parents."""
    AwareBaseTest.teardown_test(self)
    RttBaseTest.teardown_test(self)

#############################################################################

  def run_rtt_discovery(self, init_dut, resp_mac=None, resp_peer_id=None):
    """Perform single RTT measurement, using Aware, from the Initiator DUT to
    a Responder. The RTT Responder can be specified using its MAC address
    (obtained using out- of-band discovery) or its Peer ID (using Aware
    discovery).

    Args:
      init_dut: RTT Initiator device
      resp_mac: MAC address of the RTT Responder device
      resp_peer_id: Peer ID of the RTT Responder device
    """
    asserts.assert_true(resp_mac is not None or resp_peer_id is not None,
                        "One of the Responder specifications (MAC or Peer ID)"
                        " must be provided!")
    if resp_mac is not None:
      id = init_dut.droid.wifiRttStartRangingToAwarePeerMac(resp_mac)

    else:
      id = init_dut.droid.wifiRttStartRangingToAwarePeerId(resp_peer_id)
    try:
      event = init_dut.ed.pop_event(rutils.decorate_event(
          rconsts.EVENT_CB_RANGING_ON_RESULT, id), rutils.EVENT_TIMEOUT)
      if resp_mac is not None:
        rutils.validate_aware_mac_result(
            event["data"][rconsts.EVENT_CB_RANGING_KEY_RESULTS][0], resp_mac,
            "DUT")
      else:
        rutils.validate_aware_peer_id_result(
            event["data"][rconsts.EVENT_CB_RANGING_KEY_RESULTS][0],
            resp_peer_id, "DUT")
      return event
    except queue.Empty:
      return None

  def run_rtt_ib_discovery_set(self, do_both_directions, iter_count,
      time_between_iterations, time_between_roles):
    """Perform a set of RTT measurements, using in-band (Aware) discovery.

    Args:
      do_both_directions: False - perform all measurements in one direction,
                          True - perform 2 measurements one in both directions.
      iter_count: Number of measurements to perform.
      time_between_iterations: Number of seconds to wait between iterations.
      time_between_roles: Number of seconds to wait when switching between
                          Initiator and Responder roles (only matters if
                          do_both_directions=True).

    Returns: a list of the events containing the RTT results (or None for a
    failed measurement). If both directions are tested then returns a list of
    2 elements: one set for each direction.
    """
    p_dut = self.android_devices[0]
    s_dut = self.android_devices[1]

    (p_id, s_id, p_disc_id, s_disc_id,
     peer_id_on_sub, peer_id_on_pub) = autils.create_discovery_pair(
        p_dut,
        s_dut,
        p_config=autils.create_discovery_config(
            self.SERVICE_NAME, aconsts.PUBLISH_TYPE_UNSOLICITED),
        s_config=autils.create_discovery_config(
            self.SERVICE_NAME, aconsts.SUBSCRIBE_TYPE_PASSIVE),
        device_startup_offset=self.device_startup_offset,
        msg_id=self.get_next_msg_id())

    eventsPS = []
    eventsSP = []
    for i in range(iter_count):
      if i != 0 and time_between_iterations != 0:
        time.sleep(time_between_iterations)

      # perform RTT from pub -> sub
      eventsPS.append(
        self.run_rtt_discovery(p_dut, resp_peer_id=peer_id_on_pub))

      if do_both_directions:
        if time_between_roles != 0:
          time.sleep(time_between_roles)

        # perform RTT from sub -> pub
        eventsSP.append(
          self.run_rtt_discovery(s_dut, resp_peer_id=peer_id_on_sub))

    return eventsPS if not do_both_directions else [eventsPS, eventsSP]

  def run_rtt_oob_discovery_set(self, do_both_directions, iter_count,
      time_between_iterations, time_between_roles):
    """Perform a set of RTT measurements, using out-of-band discovery.

    Args:
      do_both_directions: False - perform all measurements in one direction,
                          True - perform 2 measurements one in both directions.
      iter_count: Number of measurements to perform.
      time_between_iterations: Number of seconds to wait between iterations.
      time_between_roles: Number of seconds to wait when switching between
                          Initiator and Responder roles (only matters if
                          do_both_directions=True).

    Returns: a list of the events containing the RTT results (or None for a
    failed measurement). If both directions are tested then returns a list of
    2 elements: one set for each direction.
    """
    dut0 = self.android_devices[0]
    dut1 = self.android_devices[1]

    id0, mac0 = autils.attach_with_identity(dut0)
    id1, mac1 = autils.attach_with_identity(dut1)

    # wait for for devices to synchronize with each other - there are no other
    # mechanisms to make sure this happens for OOB discovery (except retrying
    # to execute the data-path request)
    time.sleep(autils.WAIT_FOR_CLUSTER)

    events01 = []
    events10 = []
    for i in range(iter_count):
      if i != 0 and time_between_iterations != 0:
        time.sleep(time_between_iterations)

      # perform RTT from dut0 -> dut1
      events01.append(
          self.run_rtt_discovery(dut0, resp_mac=mac1))

      if do_both_directions:
        if time_between_roles != 0:
          time.sleep(time_between_roles)

        # perform RTT from dut1 -> dut0
        events10.append(
            self.run_rtt_discovery(dut1, resp_mac=mac0))

    return events01 if not do_both_directions else [events01, events10]

  def verify_results(self, events, events_reverse_direction=None):
    """Verifies the results of the RTT experiment.

    Args:
      events: List of RTT result events.
      events_reverse_direction: List of RTT result events executed in the
                                reverse direction. Optional.
    """
    stats = rutils.extract_stats(events, self.rtt_reference_distance_mm,
                          self.DISTANCE_MARGIN, self.MAX_EXPECTED_RSSI)
    stats_reverse_direction = None
    if events_reverse_direction is not None:
      stats_reverse_direction = rutils.extract_stats(events_reverse_direction,
          self.rtt_reference_distance_mm, self.DISTANCE_MARGIN,
          self.MAX_EXPECTED_RSSI)
    self.log.info("Stats: %s", stats)
    if stats_reverse_direction is not None:
      self.log.info("Stats in reverse direction: %s", stats_reverse_direction)
    asserts.explicit_pass("RTT Aware test done",
                          extras=(stats, stats_reverse_direction))

  #############################################################################

  def test_rtt_oob_discovery_one_way(self):
    """Perform RTT between 2 Wi-Fi Aware devices. Use out-of-band discovery
    to communicate the MAC addresses to the peer. Test one-direction RTT only.
    """
    rtt_events = self.run_rtt_oob_discovery_set(do_both_directions=False,
          iter_count=self.NUM_ITER,
          time_between_iterations=self.TIME_BETWEEN_ITERATIONS,
          time_between_roles=self.TIME_BETWEEN_ROLES)
    self.verify_results(rtt_events)

  def test_rtt_oob_discovery_both_ways(self):
    """Perform RTT between 2 Wi-Fi Aware devices. Use out-of-band discovery
    to communicate the MAC addresses to the peer. Test RTT both-ways:
    switching rapidly between Initiator and Responder.
    """
    rtt_events1, rtt_events2 = self.run_rtt_oob_discovery_set(
        do_both_directions=True, iter_count=self.NUM_ITER,
        time_between_iterations=self.TIME_BETWEEN_ITERATIONS,
        time_between_roles=self.TIME_BETWEEN_ROLES)
    self.verify_results(rtt_events1, rtt_events2)

  def test_rtt_ib_discovery_one_way(self):
    """Perform RTT between 2 Wi-Fi Aware devices. Use in-band (Aware) discovery
    to communicate the MAC addresses to the peer. Test one-direction RTT only.
    """
    rtt_events = self.run_rtt_ib_discovery_set(do_both_directions=False,
           iter_count=self.NUM_ITER,
           time_between_iterations=self.TIME_BETWEEN_ITERATIONS,
           time_between_roles=self.TIME_BETWEEN_ROLES)
    self.verify_results(rtt_events)

  def test_rtt_ib_discovery_both_ways(self):
    """Perform RTT between 2 Wi-Fi Aware devices. Use in-band (Aware) discovery
    to communicate the MAC addresses to the peer. Test RTT both-ways:
    switching rapidly between Initiator and Responder.
    """
    rtt_events1, rtt_events2 = self.run_rtt_ib_discovery_set(
        do_both_directions=True, iter_count=self.NUM_ITER,
        time_between_iterations=self.TIME_BETWEEN_ITERATIONS,
        time_between_roles=self.TIME_BETWEEN_ROLES)
    self.verify_results(rtt_events1, rtt_events2)