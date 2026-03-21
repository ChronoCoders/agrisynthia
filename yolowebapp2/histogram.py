# -*- coding: utf-8 -*-
"""
Vegetation Index Calculator for Remote Sensing
Implements 24 vegetation indices with optimized class-based architecture
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import rasterio
from rio_tiler.colormap import cmap
from rio_tiler.io import Reader
from rio_tiler.utils import linear_rescale

# Suppress numpy warnings for division by zero and invalid values
np.seterr(divide="ignore", invalid="ignore")

BASE_DIR = Path(__file__).resolve().parent.parent


def get_zoom(raster_path: str) -> Dict[str, int]:
    """Get zoom levels and band count for a raster file."""
    with Reader(raster_path) as src:
        info = src.info()
        band_count = src.dataset.meta["count"]
        minzoom, maxzoom = info["minzoom"], info["maxzoom"]
        maxzoom = max(maxzoom, minzoom)
    return {"minzoom": minzoom, "maxzoom": maxzoom, "band_count": band_count}


class VegetationIndex(ABC):
    """
    Abstract base class for vegetation indices.

    All vegetation index implementations must subclass this and implement calculate().
    """

    def __init__(
        self, red: np.ndarray, green: np.ndarray, blue: np.ndarray, nir: np.ndarray
    ):
        """
        Initialize with band data.

        Args:
            red: Red band as float32 array
            green: Green band as float32 array
            blue: Blue band as float32 array
            nir: NIR band as float32 array
        """
        self.red = red.astype(np.float32)
        self.green = green.astype(np.float32)
        self.blue = blue.astype(np.float32)
        self.nir = nir.astype(np.float32)

    @abstractmethod
    def calculate(self) -> np.ndarray:
        """Calculate the vegetation index. Must be implemented by subclasses."""
        pass

    def get_name(self) -> str:
        """Get the index name from class name."""
        return self.__class__.__name__


# =============================================================================
# Vegetation Index Implementations (24 indices)
# =============================================================================


class NDVI(VegetationIndex):
    """Normalized Difference Vegetation Index: (NIR - R) / (NIR + R)"""

    def calculate(self) -> np.ndarray:
        return (self.nir - self.red) / (self.nir + self.red)


class VARI(VegetationIndex):
    """Visible Atmospherically Resistant Index: (G - R) / (G + R - B)"""

    def calculate(self) -> np.ndarray:
        return (self.green - self.red) / (self.green + self.red - self.blue)


class GLI(VegetationIndex):
    """Green Leaf Index: ((G * 2) - R - B) / ((G * 2) + R + B)"""

    def calculate(self) -> np.ndarray:
        return ((self.green * 2) - self.red - self.blue) / (
            (self.green * 2) + self.red + self.blue
        )


class NDYI(VegetationIndex):
    """Normalized Difference Yellowness Index: (G - B) / (G + B)"""

    def calculate(self) -> np.ndarray:
        return (self.green - self.blue) / (self.green + self.blue)


class NDRE(VegetationIndex):
    """Normalized Difference Red Edge: (NIR - R) / (NIR + R)"""

    def calculate(self) -> np.ndarray:
        return (self.nir - self.red) / (self.nir + self.red)


class NDWI(VegetationIndex):
    """Normalized Difference Water Index: (G - NIR) / (NIR + G)"""

    def calculate(self) -> np.ndarray:
        return (self.green - self.nir) / (self.nir + self.green)


class NDVI_Blue(VegetationIndex):
    """NDVI using Blue band: (NIR - B) / (NIR + B)"""

    def calculate(self) -> np.ndarray:
        return (self.nir - self.blue) / (self.nir + self.blue)


class ENDVI(VegetationIndex):
    """Enhanced NDVI: ((NIR + G) - (2 * B)) / ((NIR + G) + (2 * B))"""

    def calculate(self) -> np.ndarray:
        return ((self.nir + self.green) - (2 * self.blue)) / (
            (self.nir + self.green) + (2 * self.blue)
        )


class VNDVI(VegetationIndex):
    """Visible NDVI: 0.5268*((R ** -0.1294) * (G ** 0.3389) * (B ** -0.3118))"""

    def calculate(self) -> np.ndarray:
        return 0.5268 * (
            (self.red**-0.1294) * (self.green**0.3389) * (self.blue**-0.3118)
        )


class MPRI(VegetationIndex):
    """Modified Photochemical Reflectance Index: (G - R) / (G + R)"""

    def calculate(self) -> np.ndarray:
        return (self.green - self.red) / (self.green + self.red)


class EXG(VegetationIndex):
    """Excess Green Index: (2 * G) - (R + B)"""

    def calculate(self) -> np.ndarray:
        return (2 * self.green) - (self.red + self.blue)


class TGI(VegetationIndex):
    """Triangular Greenness Index: (G - 0.39) * (R - 0.61) * B"""

    def calculate(self) -> np.ndarray:
        return (self.green - 0.39) * (self.red - 0.61) * self.blue


class BAI(VegetationIndex):
    """Burn Area Index: 1.0 / (((0.1 - R) ** 2) + ((0.06 - NIR) ** 2))"""

    def calculate(self) -> np.ndarray:
        return 1.0 / (((0.1 - self.red) ** 2) + ((0.06 - self.nir) ** 2))


class GNDVI(VegetationIndex):
    """Green NDVI: (NIR - G) / (NIR + G)"""

    def calculate(self) -> np.ndarray:
        return (self.nir - self.green) / (self.nir + self.green)


class GRVI(VegetationIndex):
    """Green Ratio Vegetation Index: NIR / G"""

    def calculate(self) -> np.ndarray:
        return self.nir / self.green


class SAVI(VegetationIndex):
    """Soil Adjusted Vegetation Index: (1.5 * (NIR - R)) / (NIR + R + 0.5)"""

    def calculate(self) -> np.ndarray:
        return (1.5 * (self.nir - self.red)) / (self.nir + self.red + 0.5)


class MNLI(VegetationIndex):
    """Modified Non-Linear Index: ((NIR ** 2 - R) * 1.5) / (NIR ** 2 + R + 0.5)"""

    def calculate(self) -> np.ndarray:
        return ((self.nir**2 - self.red) * 1.5) / (self.nir**2 + self.red + 0.5)


class MSR(VegetationIndex):
    """Modified Simple Ratio: ((NIR / R) - 1) / (sqrt(NIR / R) + 1)"""

    def calculate(self) -> np.ndarray:
        return ((self.nir / self.red) - 1) / (np.sqrt(self.nir / self.red) + 1)


class RDVI(VegetationIndex):
    """Renormalized Difference Vegetation Index: (NIR - R) / sqrt(NIR + R)"""

    def calculate(self) -> np.ndarray:
        return (self.nir - self.red) / np.sqrt(self.nir + self.red)


class TDVI(VegetationIndex):
    """Transformed Difference Vegetation Index: 1.5 * ((NIR - R) / sqrt(NIR ** 2 + R + 0.5))"""

    def calculate(self) -> np.ndarray:
        return 1.5 * ((self.nir - self.red) / np.sqrt(self.nir**2 + self.red + 0.5))


class OSAVI(VegetationIndex):
    """Optimized Soil Adjusted Vegetation Index: (NIR - R) / (NIR + R + 0.16)"""

    def calculate(self) -> np.ndarray:
        return (self.nir - self.red) / (self.nir + self.red + 0.16)


class LAI(VegetationIndex):
    """Leaf Area Index: 3.618 * (2.5 * (NIR - R) / (NIR + 6*R - 7.5*B + 1)) * 0.118"""

    def calculate(self) -> np.ndarray:
        return (
            3.618
            * (
                2.5
                * (self.nir - self.red)
                / (self.nir + 6 * self.red - 7.5 * self.blue + 1)
            )
            * 0.118
        )


class EVI(VegetationIndex):
    """Enhanced Vegetation Index: 2.5 * (NIR - R) / (NIR + 6*R - 7.5*B + 1)"""

    def calculate(self) -> np.ndarray:
        return (
            2.5
            * (self.nir - self.red)
            / (self.nir + 6 * self.red - 7.5 * self.blue + 1)
        )


class ARVI(VegetationIndex):
    """Atmospherically Resistant Vegetation Index: (NIR - (2 * R) + B) / (NIR + (2 * R) + B)"""

    def calculate(self) -> np.ndarray:
        return (self.nir - (2 * self.red) + self.blue) / (
            self.nir + (2 * self.red) + self.blue
        )


# =============================================================================
# Index Registry
# =============================================================================

INDICES: Dict[str, type] = {
    "ndvi": NDVI,
    "vari": VARI,
    "gli": GLI,
    "ndyi": NDYI,
    "ndre": NDRE,
    "ndwi": NDWI,
    "ndvi_blue": NDVI_Blue,
    "endvi": ENDVI,
    "vndvi": VNDVI,
    "mpri": MPRI,
    "exg": EXG,
    "tgi": TGI,
    "bai": BAI,
    "gndvi": GNDVI,
    "grvi": GRVI,
    "savi": SAVI,
    "mnli": MNLI,
    "msr": MSR,
    "rdvi": RDVI,
    "tdvi": TDVI,
    "osavi": OSAVI,
    "lai": LAI,
    "evi": EVI,
    "arvi": ARVI,
}


# =============================================================================
# Backward Compatible Interface
# =============================================================================


class algos:
    """
    Backward compatible class for vegetation index calculations.

    Uses the new class-based architecture internally while maintaining
    the original function signatures.
    """

    def __init__(self, path: str, out: str):
        """
        Initialize with input/output paths.

        Args:
            path: Path to input raster
            out: Output directory name
        """
        self.input_path = path
        self.output_path = out
        self.raster = rasterio.open(self.input_path)

    def _iter_windows(self, tile_size: int = 1024):
        height = self.raster.height
        width = self.raster.width
        for row_off in range(0, height, tile_size):
            win_h = min(tile_size, height - row_off)
            for col_off in range(0, width, tile_size):
                win_w = min(tile_size, width - col_off)
                yield rasterio.windows.Window(col_off, row_off, win_w, win_h)

    def _process_index(
        self,
        index_class: type,
        ranges: Tuple[float, float],
        colormap: Optional[str],
        rescale: bool = True,
    ) -> Dict[str, Any]:
        """
        Generic method to process any vegetation index.

        Args:
            index_class: The vegetation index class to use
            ranges: Min/max range for rescaling
            colormap: Colormap name
            rescale: Whether to apply linear rescaling

        Returns:
            Dict with path, colormap, and ranges
        """
        cm = cmap.get(colormap or "rdylgn")
        meta = self.raster.meta
        meta.update(
            {
                "count": 1,
                "driver": "GTiff",
                "nodata": 0,
                "bins": 255,
                "dtype": np.uint16,
                "quality": 90,
            }
        )

        output_path = (
            f"{BASE_DIR}/static/results/{self.output_path}/odm_orthophoto/output.tif"
        )
        with rasterio.open(output_path, "w", **meta) as dst:
            for window in self._iter_windows():
                red = self.raster.read(1, window=window).astype(np.float32)
                green = self.raster.read(2, window=window).astype(np.float32)
                blue = self.raster.read(3, window=window).astype(np.float32)
                nir = self.raster.read(4, window=window).astype(np.float32)
                index = index_class(red, green, blue, nir)
                result = index.calculate().astype(np.float32)
                if rescale:
                    rgb = linear_rescale(result, in_range=ranges).astype(np.float32)
                else:
                    rgb = result.astype(np.float32)
                dst.write(rgb, 1, window=window)
            dst.write_colormap(1, cm)

        return {
            "path": f"results/{self.output_path}/odm_orthophoto/output.tif",
            "colormap": colormap,
            "ranges": ranges,
        }

    # Keep original method names for backward compatibility
    def Ndvi(
        self, ranges: Tuple[float, float] = (-1, 1), colormap: Optional[str] = None
    ) -> Dict[str, Any]:
        if ranges == (-0.0, 0.0):
            ranges = (-0.5, 1)
        return self._process_index(NDVI, ranges, colormap)

    def Vari(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(VARI, ranges, colormap)

    def Gli(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(GLI, ranges, colormap)

    def NDYI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(NDYI, ranges, colormap)

    def NDRE(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(NDRE, ranges, colormap)

    def NDWI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(NDWI, ranges, colormap)

    def NDVI_Blue(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(NDVI_Blue, ranges, colormap)

    def ENDVI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(ENDVI, ranges, colormap)

    def VNDVI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(VNDVI, ranges, colormap)

    def MPRI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(MPRI, ranges, colormap)

    def EXG(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(EXG, ranges, colormap, rescale=False)

    def TGI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(TGI, ranges, colormap)

    def BAI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(BAI, ranges, colormap)

    def GNDVI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(GNDVI, ranges, colormap)

    def GRVI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(GRVI, ranges, colormap)

    def SAVI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(SAVI, ranges, colormap)

    def MNLI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(MNLI, ranges, colormap)

    def MSR(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(MSR, ranges, colormap)

    def RDVI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(RDVI, ranges, colormap)

    def TDVI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(TDVI, ranges, colormap)

    def OSAVI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(OSAVI, ranges, colormap)

    def LAI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(LAI, ranges, colormap)

    def EVI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(EVI, ranges, colormap)

    def ARVI(
        self, ranges: Tuple[float, float], colormap: Optional[str]
    ) -> Dict[str, Any]:
        return self._process_index(ARVI, ranges, colormap)


# =============================================================================
# Legacy standalone functions (kept for backward compatibility)
# =============================================================================


def gli(path: str) -> np.ndarray:
    """Legacy GLI function for PIL Image input."""
    from PIL import Image

    img = Image.open(path)
    arr = np.asarray(img).astype(float)
    gli_array = (2 * arr[:, :, 1] - arr[:, :, 0] - arr[:, :, 2]) / (
        2 * arr[:, :, 1] + arr[:, :, 0] + arr[:, :, 2]
    )
    gli_array[np.isnan(gli_array)] = 0
    return gli_array


def vari(path: str) -> np.ndarray:
    """Legacy VARI function for PIL Image input."""
    from PIL import Image

    img = Image.open(path)
    arr = np.asarray(img).astype(float)
    vari_array = (arr[:, :, 1] - arr[:, :, 0]) / (
        arr[:, :, 1] + arr[:, :, 0] - arr[:, :, 2]
    )
    vari_array[np.isnan(vari_array)] = 0
    return vari_array


def vigreen(path: str) -> np.ndarray:
    """Legacy VI Green function for PIL Image input."""
    from PIL import Image

    img = Image.open(path)
    arr = np.asarray(img).astype(float)
    vi_array = (arr[:, :, 1] - arr[:, :, 0]) / (arr[:, :, 1] + arr[:, :, 0])
    vi_array[np.isnan(vi_array)] = 0
    return vi_array


def ndvi(path: str) -> np.ndarray:
    """Legacy NDVI function for PIL Image input."""
    from PIL import Image

    img = Image.open(path)
    arr = np.asarray(img).astype(float)
    ndvi_array = (arr[:, :, 2] - arr[:, :, 0]) / (arr[:, :, 2] + arr[:, :, 0])
    ndvi_array[np.isnan(ndvi_array)] = 0
    return ndvi_array


def hist(path: str) -> Tuple[np.ndarray, np.ndarray]:
    """Calculate histogram for image."""
    import cv2

    img = cv2.imread(path)
    hist, bins = np.histogram(img.ravel(), 256, (0, 256))
    return hist, bins
