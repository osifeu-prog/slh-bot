from core.kernel import SLHKernel
from core.runtime import Runtime
from adapters.cli import CLIAdapter
from agents.echo import EchoAgent

def main():
    kernel = SLHKernel()

    kernel.register("echo", EchoAgent())

    runtime = Runtime(kernel)
    runtime.start()

    cli = CLIAdapter(runtime)
    cli.run()

if __name__ == "__main__":
    main()
