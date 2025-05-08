from loguru import logger
from tqdm import tqdm

from amsl_labjack_pipeline.parser import invoke
from amsl_labjack_pipeline.stages.convert import Convert as Params


def main(params: Params):
    logger.info("start convert")
    for _source in tqdm(sorted(params.deps.cines.iterdir())):
        pass
    logger.info("finish convert")


if __name__ == "__main__":
    invoke(Params)
