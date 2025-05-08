from loguru import logger
from tqdm import tqdm

from amsl_labjack_pipeline.parser import invoke
from amsl_labjack_pipeline.stages.binarize import Binarize as Params


def main(params: Params):
    logger.info("start binarize")
    for _source in tqdm(sorted(params.deps.large_sources.iterdir())):
        pass
    logger.info("finish binarize")


if __name__ == "__main__":
    invoke(Params)
