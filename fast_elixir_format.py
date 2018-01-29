import sublime
import sublime_plugin
import subprocess
import os
from os.path import dirname, realpath
import http.client
import base64

PLUGIN_PATH = dirname(realpath(__file__))
servers = {}

def plugin_unloaded():
  for server in servers.values():
    server.close()

class FormatServer:
  def __init__(self, folder):
    self.folder = folder
    env = os.environ.copy()
    server_cmd = ["elixir", PLUGIN_PATH + "/format_server.exs"]

    self.proc = subprocess.Popen(server_cmd, stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE, env = env, cwd = folder)
    self.port = int(self.proc.stdout.readline())
    print("Started Elixir format server (pid: %d, port: %d)" % (self.proc.pid, self.port))

  def close(self):
    print("Killing Elixir format server (pid: %d)" % self.proc.pid)
    self.proc.kill()

  def execute(self, text):
    try:
      conn = http.client.HTTPConnection("localhost", self.port)
      conn.request("POST", "/", text)
      response = conn.getresponse()
      if response.status != 200:
        return False

      body = response.read().decode('UTF-8')
      conn.close()

      lines = body.splitlines()
      lines.reverse()
      commands = []

      while len(lines) > 0:
        cmd = lines.pop()
        text = base64.b64decode(lines.pop()).decode('UTF-8')
        commands.append((cmd, text))

      return commands
    except:
      del servers[self.folder]
      raise


def server_for_folder(folder):
  if folder not in servers:
    print("Elixir format server not found for directory " + folder)
    servers[folder] = FormatServer(folder)

  return servers[folder]


class FastElixirFormatCommand(sublime_plugin.TextCommand):
  def is_enabled(self):
    caret = self.view.sel()[0].a
    syntax_name = self.view.scope_name(caret)
    return "source.elixir" in syntax_name

  def run(self, edit):
    folder = self.view.window().folders()[0]
    server = server_for_folder(folder)

    vsize = self.view.size()
    region = sublime.Region(0, vsize)
    src = self.view.substr(region)

    diff = server.execute(src)
    if not diff:
      print("Could not format")
      return

    pos = 0
    for op, text in diff:
      if op == 'eq':
        # TODO: check the region matches with the expected code
        pos += len(text)
      if op == 'del':
        # TODO: check the region matches with the expected code
        region = sublime.Region(pos, pos + len(text))
        self.view.replace(edit, region, '')
      if op == 'ins':
        region = sublime.Region(pos, pos)
        self.view.replace(edit, region, text)
        pos += len(text)

class FastElixirEventListener(sublime_plugin.EventListener):
  @staticmethod
  def on_pre_save(view):
    cmd, args, repeat = view.command_history(1)
    if cmd == '':
      view.run_command('fast_elixir_format')
