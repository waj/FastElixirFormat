require Mix.Task
Mix.Task.load_all()
:inets.start()

defmodule FormatServer do
  require Record
  Record.defrecord(:mod, Record.extract(:mod, from_lib: "inets/include/httpd.hrl"))

  def start() do
    {:ok, pid} =
      :inets.start(
        :httpd,
        port: 0,
        server_name: 'elixir_format',
        server_root: '/tmp',
        document_root: '/tmp',
        modules: [FormatServer]
      )

    :httpd.info(pid)[:port]
  end

  def unquote(:do)(mod(method: 'POST', entity_body: code)) do
    code = IO.iodata_to_binary(code)

    response =
      case format(code) do
        :error ->
          {400, ''}

        diff ->
          {200, diff |> String.to_charlist()}
      end

    {:proceed, [{:response, response}]}
  end

  defp format(code) do
    temp_file = "/tmp/format_#{:rand.uniform(10_000_000)}.ex"
    File.write!(temp_file, code)

    try do
      format_task = Mix.Task.get("format")
      format_task.run([temp_file])
      new_code = File.read!(temp_file)

      String.myers_difference(code, new_code)
      |> write_diff
    catch
      :exit, _error ->
        :error
    after
      File.rm!(temp_file)
    end
  end

  def write_diff(diff, acc \\ <<>>)
  def write_diff([], acc), do: acc

  def write_diff([{op, text} | diff], acc) do
    write_diff(diff, acc <> "#{op}\n#{text |> Base.encode64()}\n")
  end
end

port = FormatServer.start()
IO.puts(port)
IO.read(:line)
