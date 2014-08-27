#!/usr/bin/python3.4
# vim:ts=4:sw=4:softtabstop=4:smarttab:expandtab

#   Copyright 2014 - The Android Open Source Project
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

import itertools
import json
import os
from queue import Empty

from base_test import BaseTestClass
from test_utils.utils import load_config
from test_utils.wifi_test_utils import start_wifi_background_scan
from test_utils.wifi_test_utils import wifi_toggle_state
from test_utils.wifi_test_utils import WifiEnums

SCANCHANNEL = [2412,2437,2457,2462,5180,5200,5220,5745]
SCANTIME = 10000

EVENT_TAG = "WifiScannerScan"

class WifiScannerScanError(Exception):
  pass

class WifiScannerScanTest(BaseTestClass):
  TAG = "WifiScannerScanTest"
  current_path = os.path.dirname(os.path.abspath(__file__))
  log_path = ''.join((BaseTestClass.log_path, TAG, '/'))

  def __init__(self, controllers):
    BaseTestClass.__init__(self, self.TAG, controllers)
    self.failed_scan_settings = None
    # A list of all test cases to be executed in this class.
    self.tests = (
        "test_wifi_scanner_scan_with_enumerated_params",
        "test_wifi_scanner_with_wifi_off",
        "test_wifi_scanner_with_invalid_numBssidsPerScan",
        "test_wifi_scanner_scan_with_failed_settings",
        "test_wifi_scanner_scan_sanity"
        )

  def setup_class(self):
    BaseTestClass.setup_class(self)
    if not hasattr(self, "access_points"):
      self.log.error("No AP available.")
      return False
    self.config = load_config(self.current_path
                              + "/WifiScannerTests.config")
    ap_configs = self.config["AP"]
    if len(self.access_points) < len(ap_configs):
      self.log.error("Not enough APs to config.")
      return False
    # Initialize APs with config file.
    configured = []
    for item in ap_configs:
      self.log.info("Setting up AP " + str(item["index"]))
      self.access_points[item["index"]].apply_configs(item)
      configured.append(item["index"])
    # If more APs exist than needed, disable extras.
    if len(self.access_points) > len(ap_configs):
      for idx,ap in enumerate(self.access_points):
        if idx not in configured:
          self.access_points[idx].toggle_radio_state("radio0", False)
          self.access_points[idx].toggle_radio_state("radio1", False)
    return True

  def teardown_test(self):
    BaseTestClass.teardown_test(self)
    self.log.debug("Shut down all wifi scanner activities.")
    self.droid.wifiScannerShutdown()

  # def setup_class(self):
  #   return True

  """ Helper Functions Begin """

  def wifi_generate_scanner_scan_settings(self):
    """Generates all the combinations of different scan setting parameters.

    Returns:
      A list of dictionaries each representing a set of scan settings.
    """
    base_scan_setting = {"periodInMs": SCANTIME}
    report_types = (WifiEnums.REPORT_EVENT_AFTER_BUFFER_FULL,
                    WifiEnums.REPORT_EVENT_AFTER_EACH_SCAN,
                    WifiEnums.REPORT_EVENT_FULL_SCAN_RESULT)
    scan_types = (("band", WifiEnums.WIFI_BAND_BOTH_WITH_DFS),
                  ("band", WifiEnums.WIFI_BAND_24_GHZ),
                  ("band", WifiEnums.WIFI_BAND_5_GHZ),
                  ("channels", WifiEnums.NONE_DFS_5G_FREQUENCIES),
                  ("channels", WifiEnums.ALL_2G_FREQUENCIES),
                  ("channels", SCANCHANNEL))
    num_of_bssid = (16,)
    # Generate all the combinations of report types and scan types
    setting_combinations = list(itertools.product(report_types,
                                                  scan_types,
                                                  num_of_bssid))
    # Create scan setting strings based on the combinations
    scan_settings = []
    for combo in setting_combinations:
      s = dict(base_scan_setting)
      s["reportEvents"] = combo[0]
      s[combo[1][0]] = combo[1][1]
      s["numBssidsPerScan"] = combo[2]
      scan_settings.append(s)
    return scan_settings

  def filter_wifi_info_by_freq(self, scan_setting, infos):
    freq_filter = None
    if "band" in scan_setting and "channels" not in scan_setting:
      freq_filter = WifiEnums.band_to_frequencies[scan_setting["band"]]
    elif "channels" in scan_setting and "band" not in scan_setting:
      freq_filter = scan_setting["channels"]
    filtered_infos = []
    extra_infos = []
    for i in infos:
      if i["frequency"] in freq_filter:
        filtered_infos.append(i)
      else:
        extra_infos.append(i)
    return filtered_infos, extra_infos

  def wifi_generate_expected_wifi_infos(self, scan_setting):
    infos = []
    for ap in self.access_points:
      infos += ap.get_active_ssids_info("frequency")
    expected, _ = self.filter_wifi_info_by_freq(scan_setting, infos)
    return expected

  def verify_one_scan_result(self, expected, result):
    for k, v in expected.items():
      if k == "device": # skip "device" since it will never be in results.
        continue
      if k not in result or v != result[k]:
        self.log.error(' '.join(("Mismatching", k, "expected", v, "got",
                       str(result[k]))))
        return False
    return True

  def verify_scan_results(self, expected, scan_results):
    # TODO(angli): Add support for bssid oriented check. Right now we don't
    # support duplicated ssid in results
    results = {}
    status = True
    # Create a look up dict so we can easily look up result by ssid.
    for r in scan_results:
      results[r["ssid"]] = r
    for exp in expected:
      ssid = exp["ssid"]
      if ssid not in results:
        status = False
        self.log.error("Missing\n" + str(exp))
      else:
        s = self.verify_one_scan_result(exp, results[ssid])
        if not s:
          status = False
          self.log.error("Mismatch occurred, expected\n" + str(exp) + "\nGot\n"
                         + str(results[ssid]))
    return status

  def result_sanity_check(self, scan_setting, infos):
    _, extras = self.filter_wifi_info_by_freq(scan_setting, infos)
    if extras:
      self.log.error("Found unexpected entries in scan results:\n"
                     + str(extras))
      return False
    return True

  def wifi_execute_one_scan_test(self, scan_setting):
    """Common logic for an enumerated wifi scanner scan test case.

    This function starts a scan with the given settings, queries the access
    points for active wifi networks, infers expected results from the active
    networks and scan setting, and verifies the actual results.

    There are two steps for the verification. First it checks that all the
    wifi networks in results are of the correct frequencies set by scan setting
    params. Then it checks that the results contain all the active wifi
    networks with the correct frequencies broadcasted by the APs.

    Args:
      scan_setting: The params for the background scan.

    Returns:
      True if the test passes, False otherwise.
    """
    idx = None
    results = None
    try:
      idx = start_wifi_background_scan(self.droid, self.ed, scan_setting)
      self.log.debug("Wifi background scan started with index: " + str(idx))
      event = self.ed.pop_event(''.join((EVENT_TAG, str(idx), "onResults")), 300)
      results = event["data"]["Results"]
      self.log.debug("Got onResults:\n" + str(event))
    except Empty:
      events = self.ed.pop_events(EVENT_TAG, 10)
      self.log.error("Did not get onSuccess, got:\n" + str(events))
      return False
    finally:
      self.droid.wifiScannerStopScan(idx)
      self.ed.clear_all_events()
    # First make sure all results are of the expected frequencies.
    if not self.result_sanity_check(scan_setting, results):
      return False
    # Now check to make sure all expected wifi networks are found in results.
    expected = self.wifi_generate_expected_wifi_infos(scan_setting)
    self.log.debug("Expected results:\n" + str(expected))
    return self.verify_scan_results(expected, results)

  def start_wifi_scanner_scan_expect_failure(self, scan_setting):
    try:
      idx = self.droid.wifiScannerStartScan(json.dumps(scan_setting))
      event = self.ed.pop_event(''.join((EVENT_TAG, str(idx), "onFailure")),
                                WifiEnums.SHORT_TIMEOUT)
    except Empty:
      events = self.ed.pop_events(EVENT_TAG, WifiEnums.SHORT_TIMEOUT)
      self.log.error("Did not get expected onFailure. Got\n" + str(events))
      return False
    self.log.debug("Got expected onFailure:\n" + str(event))
    return True

  def check_get_available_channels_with_one_band(self, b):
    r = self.droid.wifiScannerGetAvailableChannels(b)
    self.log.debug(b)
    self.log.debug(r)
    expected = WifiEnums.band_to_frequencies[b]
    if not r or set(r) != set(expected):
      self.log.error(' '.join(("Band", str(b), "failed. Expected",
                               str(expected), "got", str(r))))
      return False
    return True
  """ Helper Functions End """

  """ Tests Begin """
  # The two test_available_channels tests demonstrate the use of generated
  # test cases. The two test cases are equivalent to each other, but the
  # generated one handles exception and reporting better.
  def test_available_channels_loop(self):
    bands = (1,2,3,4,6,7)
    for b in bands:
      r = self.droid.wifiScannerGetAvailableChannels(b)
      self.log.debug(b)
      self.log.debug(r)
      if r != WifiEnums.band_to_frequencies[b]:
        self.log.error(' '.join(("Band", str(b), "failed. Expected",
                                 str(WifiEnums.band_to_frequencies[b]),
                                 "got", str(r))))
    return False

  def test_available_channels_generated(self):
    bands = (1,2,3,4,6,7)
    failed = self.run_generated_testcases(
      "Wifi Scanner Get Available Channels",
      self.check_get_available_channels_with_one_band,
      bands)
    if failed:
      self.log.debug("Get available channels failed with these bands: "
                     + str(failed))
      return False
    return True

  def test_wifi_scanner_scan_with_enumerated_params(self, scan_settings=None):
    """Run scanner scan test with a list of different settings."""
    wifi_toggle_state(self.droid, self.ed, True)
    if not scan_settings:
      scan_settings = self.wifi_generate_scanner_scan_settings()
    self.log.debug("Scan settings:\n" + str(scan_settings))
    failed = self.run_generated_testcases("Wifi Background Scan Test",
                                          self.wifi_execute_one_scan_test,
                                          scan_settings)
    self.failed_scan_settings = failed
    self.log.debug("Settings that caused failure: " + str(failed))
    if len(failed) == 0:
      return True
    return False

  def test_wifi_scanner_scan_with_failed_settings(self):
    self.log.debug("\n===== Running the failed cases again. =====\n")
    return self.test_wifi_scanner_scan_with_enumerated_params(
      self.failed_scan_settings)

  def test_wifi_scanner_scan_sanity(self):
    scan_setting = {
      "band": WifiEnums.WIFI_BAND_BOTH_WITH_DFS,
      "periodInMs": SCANTIME,
      "reportEvents": WifiEnums.REPORT_EVENT_AFTER_EACH_SCAN
    }
    wifi_toggle_state(self.droid, self.ed, True)
    try:
      idx = start_wifi_background_scan(self.droid, self.ed, scan_setting)
      self.log.debug("Wifi background scan started with index: " + str(idx))
      event = self.ed.pop_event(''.join((EVENT_TAG, str(idx), "onResults")), 300)
      results = event["data"]["Results"]
      self.log.debug("Got onResults:\n" + str(event))
      return True
    except Empty:
      events = self.ed.pop_events(EVENT_TAG, 10)
      self.log.error("Did not get expected event, got:\n" + str(events))
      return False
    finally:
      self.droid.wifiScannerStopScan(idx)
      self.ed.clear_all_events()

  def test_wifi_scanner_with_wifi_off(self):
    self.log.debug("Make sure wifi is off.")
    wifi_toggle_state(self.droid, self.ed, False)
    scan_setting = {
      "band": WifiEnums.WIFI_BAND_BOTH_WITH_DFS,
      "periodInMs": SCANTIME,
      "reportEvents": WifiEnums.REPORT_EVENT_AFTER_EACH_SCAN
    }
    status = self.start_wifi_scanner_scan_expect_failure(scan_setting)
    self.log.debug("Turning wifi back on.")
    wifi_toggle_state(self.droid, self.ed, True)
    return status

  def test_wifi_scanner_with_invalid_numBssidsPerScan(self):
    scan_setting = {
      "band": WifiEnums.WIFI_BAND_BOTH_WITH_DFS,
      "periodInMs": SCANTIME,
      "reportEvents": WifiEnums.REPORT_EVENT_AFTER_EACH_SCAN,
      'numBssidsPerScan': 17
    }
    return self.start_wifi_scanner_scan_expect_failure(scan_setting)
  """ Tests End """

if __name__ == "__main__":
  tester = WifiScannerScanTest()
  tester.run()

