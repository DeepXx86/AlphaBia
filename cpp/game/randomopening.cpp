#include "../game/randomopening.h"

#include <algorithm>
#include <fstream>
#include <map>
#include <mutex>
#include <sstream>

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
  const PlaySettings& playSettings) {

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

    Rules gameRules = rules;
    if(playSettings.endgameCountCurriculumProb > 0.0 &&
       gameRand.nextBool(playSettings.endgameCountCurriculumProb)) {
      GameLogic::MakrukCountState count = GameLogic::getMakrukCountState(b);
      if(count.active && count.limitPlies >= 4) {
        int used = (int)gameRand.nextUInt((uint32_t)(count.limitPlies - 2));
        b.setMovenumslc(used);
        if(gameRules.maxmovesNoCapture != 0 && used + 40 > gameRules.maxmovesNoCapture)
          gameRules.maxmovesNoCapture = std::min(400, used + 40);
      }
    }

    board = b;
    nextPlayer = pla;
    hist = BoardHistory(board, pla, gameRules);
    return;
  }
}

namespace {
  struct FENEntry {
    std::string fen;
    Player pla;
    int slc;
  };
  std::mutex fenCacheMutex;
  std::map<std::string, std::vector<FENEntry>> fenCache;

  const std::vector<FENEntry>& loadFENFile(const std::string& path) {
    std::lock_guard<std::mutex> lock(fenCacheMutex);
    auto it = fenCache.find(path);
    if(it != fenCache.end())
      return it->second;
    std::vector<FENEntry>& out = fenCache[path];
    std::ifstream in(path);
    std::string line;
    while(std::getline(in, line)) {
      while(!line.empty() && (line.back() == '\r' || line.back() == '\n'))
        line.pop_back();
      std::istringstream ss(line);
      FENEntry e;
      std::string plaStr, slcStr;
      if(!(ss >> e.fen >> plaStr >> slcStr))
        continue;
      if(plaStr == "w" || plaStr == "W") e.pla = P_BLACK;
      else if(plaStr == "b" || plaStr == "B") e.pla = P_WHITE;
      else continue;
      try { e.slc = std::stoi(slcStr); }
      catch(...) { continue; }
      if(e.slc < 0 || e.slc > 400)
        e.slc = 0;
      out.push_back(e);
    }
    return out;
  }
}

bool RandomOpening::initializeFromFENFile(
  Board& board,
  BoardHistory& hist,
  Player& nextPlayer,
  Rand& gameRand,
  const PlaySettings& playSettings) {

  const std::vector<FENEntry>& entries = loadFENFile(playSettings.startFENsFile);
  if(entries.empty())
    return false;
  const Rules rules = hist.rules;

  for(int attempt = 0; attempt < 50; attempt++) {
    const FENEntry& e = entries[gameRand.nextUInt((uint32_t)entries.size())];
    Board b;
    if(!b.setFEN(e.fen, e.pla))
      continue;
    Player pla = e.pla;
    if(GameLogic::findKing(b, P_BLACK) == Board::NULL_LOC ||
       GameLogic::findKing(b, P_WHITE) == Board::NULL_LOC)
      continue;
    if(GameLogic::isInCheck(b, getOpp(pla)))
      continue;
    if(!GameLogic::hasAnyLegalMove(b, pla))
      continue;
    b.setMovenumslc(e.slc);
    Rules gameRules = rules;
    if(gameRules.maxmovesNoCapture != 0 && e.slc + 40 > gameRules.maxmovesNoCapture)
      gameRules.maxmovesNoCapture = std::min(400, e.slc + 40);

    board = b;
    nextPlayer = pla;
    hist = BoardHistory(board, pla, gameRules);
    return true;
  }
  return false;
}
