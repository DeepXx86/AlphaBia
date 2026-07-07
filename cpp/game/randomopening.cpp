#include "../game/randomopening.h"

#include "../core/rand.h"
#include "../game/board.h"
#include "../game/gamelogic.h"
#include "../search/asyncbot.h"

using namespace RandomOpening;


void RandomOpening::initializeRandomOpening(
  Search*,
  Search*,
  Board& board,
  BoardHistory& hist,
  Player& nextPlayer,
  Rand& gameRand,
  const PlaySettings&) {

  const int xs = board.x_size;
  const int ys = board.y_size;
  const Rules rules = hist.rules;

  auto cheb = [](int x1, int y1, int x2, int y2) {
    int dx = x1 > x2 ? x1 - x2 : x2 - x1;
    int dy = y1 > y2 ? y1 - y2 : y2 - y1;
    return dx > dy ? dx : dy;
  };

  for(int attempt = 0; attempt < 300; attempt++) {
    Player strong = gameRand.nextBool(0.5) ? P_BLACK : P_WHITE;
    Player weak = getOpp(strong);
    Player pla = gameRand.nextBool(0.6) ? strong : weak;

    Board b;
    if(!b.setFEN("8/8/8/8/8/8/8/8", pla))
      return; 

    auto place = [&](Player owner, Color type) {
      for(int t = 0; t < 64; t++) {
        int x = (int)gameRand.nextUInt((uint32_t)xs);
        int y = (int)gameRand.nextUInt((uint32_t)ys);
        if(type == C_BIA && (y < 2 || y > ys - 3))
          continue;
        Loc loc = Location::getLoc(x, y, xs);
        if(b.colors[loc] != C_EMPTY)
          continue;
        b.setStone(loc, getPiece(owner, type));
        return;
      }
    };

    int skx = (int)gameRand.nextUInt((uint32_t)xs);
    int sky = (int)gameRand.nextUInt((uint32_t)ys);
    b.setStone(Location::getLoc(skx, sky, xs), getPiece(strong, C_KING));
    bool wkPlaced = false;
    for(int t = 0; t < 200 && !wkPlaced; t++) {
      int x = (int)gameRand.nextUInt((uint32_t)xs);
      int y = (int)gameRand.nextUInt((uint32_t)ys);
      if(cheb(x, y, skx, sky) < 2)
        continue;
      Loc loc = Location::getLoc(x, y, xs);
      if(b.colors[loc] != C_EMPTY)
        continue;
      b.setStone(loc, getPiece(weak, C_KING));
      wkPlaced = true;
    }
    if(!wkPlaced)
      continue;

    const Color minors[3] = {C_KNIGHT, C_KHON, C_MET};
    if(gameRand.nextBool(0.6)) {
      place(strong, C_ROOK);
    } else {
      place(strong, minors[gameRand.nextUInt(3)]);
      place(strong, minors[gameRand.nextUInt(3)]);
    }
    int sbia = (int)gameRand.nextUInt(3); 
    for(int i = 0; i < sbia; i++)
      place(strong, C_BIA);

    uint32_t wr = gameRand.nextUInt(100);
    if(wr < 30)
      place(weak, minors[gameRand.nextUInt(3)]);
    else if(wr < 40)
      place(weak, C_BIA);

    if(GameLogic::isInCheck(b, pla))
      continue;
    if(GameLogic::isInCheck(b, getOpp(pla)))
      continue;
    if(!GameLogic::hasAnyLegalMove(b, pla))
      continue;

    board = b;
    nextPlayer = pla;
    hist = BoardHistory(board, pla, rules);
    return;
  }
}
