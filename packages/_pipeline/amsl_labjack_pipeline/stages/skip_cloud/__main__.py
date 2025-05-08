from amsl_labjack_pipeline.parser import invoke
from amsl_labjack_pipeline.stages.skip_cloud import SkipCloud


def main(_params: SkipCloud):
    pass


if __name__ == "__main__":
    invoke(SkipCloud)
