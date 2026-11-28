import ArchiveFixture.Left
import ArchiveFixture.Right

namespace ArchiveFixture
def answer := left + right
theorem answer_def : answer = (seed + 1) + (seed + 2) := rfl
end ArchiveFixture
