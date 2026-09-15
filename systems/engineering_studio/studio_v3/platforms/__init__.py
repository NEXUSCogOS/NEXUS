
"""
Engineering Studio Platform Layer

Compatibility exports preserved during architecture migration.
Execution ownership remains with dedicated subsystems.
"""

from .controller import *
from .monitoring_dashboard import *
from .dashboard import *

# Legacy compatibility imports
try:
    from .subtitle_generator import *
except ImportError:
    pass

try:
    from .voice_generator import *
except ImportError:
    pass

# Optional legacy YouTube interfaces
# retained only if implementation exists
try:
    from .youtube_automation import *
except ImportError:
    pass

# --------------------------------------------------
# LEGACY MIGRATION COMPATIBILITY EXPORTS
# --------------------------------------------------
# These preserve old APIs while ownership moved to
# dedicated subsystems.

from .youtube_automation import (
    ContentGenerator,
    VideoUploader,
    DataFeedConnector,
    YouTubePipeline,
    ContentPipeline,
    PublishingPipeline,
)

