#!/usr/bin/python3

import argparse
import os
import re
import subprocess
import sys


parser = argparse.ArgumentParser(description='minheader')
parser.add_argument(
  '--include-path',
  dest='include_paths',
  action='append',
  required=True)
parser.add_argument(
  '--test-command',
  dest='test_command',
  action='store',
  required=True)
parser.add_argument(
  dest='source_files',
  nargs='+')
FLAGS = parser.parse_args()


class Error(Exception):
  pass


class IncludeNotFound(Error):
  pass


class BaseTestFailed(Error):
  pass


class Interrupted(Error):
  pass


class MinHeader(object):

  _INCLUDE_RE = re.compile('^#include ["<](?P<include_path>[^>"]+\.[^>"]+)[>"]')

  def __init__(self, include_paths, test_command):
    self._include_paths = include_paths
    self._test_command = test_command

    self._Log('Initial test: ')
    if self._TestPasses():
      self._Log('PASS\n')
    else:
      self._Log('FAIL\n')
      raise BaseTestFailed

  def Minify(self, path):
    self._Log('%s:\n' % path)
    known_required = set()
    split = set()
    while self._MinifyPass(path, known_required, split):
      pass

  def _MinifyPass(self, path, known_required, split):
    lines = self._LoadFile(path)
    includes = self._FindIncludes(lines)
    for inc_i, inc_path in includes:
      if inc_path in known_required:
        continue

      self._Log('\t%s: ' % inc_path)

      try:
        sub_includes = self._FindSubIncludes(inc_path)
      except IncludeNotFound:
        self._Log('(MISSING) ')
        sub_includes = []

      # Is the include useful at all?
      if self._TestReplacement(path, lines, inc_i, []):
        self._Log('UNUSED\n')
        return True
      elif set(sub_includes) & split:
        self._Log('CIRCULAR\n')
        continue
      elif self._TestReplacement(path, lines, inc_i, sub_includes):
        self._Log('OVERBROAD\n')
        split.add(inc_path)
        return True
      else:
        self._Log('REQUIRED\n')
        known_required.add(inc_path)
        continue
    return False

  def _Log(self, msg):
    print(msg, file=sys.stderr, flush=True, end='')

  def _LoadFile(self, path):
    with open(path, 'r') as fh:
      return list(fh)

  def _WriteFile(self, path, lines):
    with open(path, 'w') as fh:
      for line in lines:
        fh.write(line)

  def _ReplaceAndWrite(self, path, lines, replace_i, replace_includes):
    new_lines = list(lines)
    new_lines[replace_i:replace_i + 1] = ['#include "%s"\n' % x for x in replace_includes]
    self._WriteFile(path, new_lines)

  def _TestReplacement(self, path, lines, replace_i, replace_includes):
    try:
      self._ReplaceAndWrite(path, lines, replace_i, replace_includes)
      if self._TestPasses():
        return True
      else:
        self._WriteFile(path, lines)
        return False
    except:
      self._WriteFile(path, lines)
      raise

  def _FindIncludes(self, lines):
    ret = []
    for i, line in enumerate(lines):
      match = self._INCLUDE_RE.match(line)
      if match:
        ret.append((i, match.group('include_path')))
    return ret

  def _FindSubIncludes(self, path):
    full_path = self._FindFile(path)
    return [x[1] for x in self._FindIncludes(self._LoadFile(full_path))]

  def _FindFile(self, path):
    for include_path in self._include_paths:
      full_path = os.path.join(include_path, path)
      if os.path.exists(full_path):
        return full_path
    raise IncludeNotFound(path)

  def _TestPasses(self):
    ret = subprocess.call(self._test_command, shell=True)
    if ret in (-2, 8):
      raise Interrupted
    return ret == 0


def main():
  minheader = MinHeader(
    FLAGS.include_paths,
    FLAGS.test_command)
  for path in FLAGS.source_files:
    minheader.Minify(path)


if __name__ == '__main__':
  main()
