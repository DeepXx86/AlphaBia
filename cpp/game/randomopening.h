#pragma once
#include "../search/asyncbot.h"
#include "../program/playsettings.h"

class Search;

namespace RandomOpening {
  //disabled
  void initializeRandomOpening(
    Search* botB,
    Search* botW,
    Board& board,
    BoardHistory& hist,
    Player& nextPlayer,
    Rand& gameRand,
    const PlaySettings& playSettings);

  //Start a game from a position in playSettings.startFENsFile (harvested FSF-failure
  //curriculum). Lines: "<engine-fen> <w|b> <movenumslc>". Returns false if no usable
  //position was found (caller keeps the standard start).
  bool initializeFromFENFile(
    Board& board,
    BoardHistory& hist,
    Player& nextPlayer,
    Rand& gameRand,
    const PlaySettings& playSettings);

}
