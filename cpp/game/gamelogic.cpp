#include "../game/gamelogic.h"

#include <algorithm>
#include <cassert>
#include <cstring>
#include <iostream>
#include <vector>

using namespace std;

int GameLogic::forwardDY(Player pla) {
  return pla == P_BLACK ? 1 : -1;
}

int GameLogic::promotionRankY(Player pla, int ySize) {
  return pla == P_BLACK ? (ySize - 3) : 2;
}

bool GameLogic::isInTrap(Loc, Player) { return false; }
bool GameLogic::isInRiver(Loc) { return false; }
Loc GameLogic::getHomeLoc(Player) { return Board::NULL_LOC; }

static bool pieceAttacksSquare(
  const Board& board, int fx, int fy, Color pt, Player byPla, int sx, int sy) {
  int dx = sx - fx;
  int dy = sy - fy;
  if(dx == 0 && dy == 0)
    return false;
  int adx = dx < 0 ? -dx : dx;
  int ady = dy < 0 ? -dy : dy;

  switch(pt) {
    case C_KING:
      return adx <= 1 && ady <= 1;
    case C_MET:
    case C_BIAGAE:
      return adx == 1 && ady == 1;
    case C_KHON: {
      if(adx == 1 && ady == 1)
        return true;
      return dx == 0 && dy == GameLogic::forwardDY(byPla);
    }
    case C_KNIGHT:
      return (adx == 1 && ady == 2) || (adx == 2 && ady == 1);
    case C_BIA:
      return adx == 1 && dy == GameLogic::forwardDY(byPla);
    case C_ROOK: {
      if(dx != 0 && dy != 0)
        return false;
      int stepx = dx == 0 ? 0 : (dx > 0 ? 1 : -1);
      int stepy = dy == 0 ? 0 : (dy > 0 ? 1 : -1);
      int cx = fx + stepx;
      int cy = fy + stepy;
      while(cx != sx || cy != sy) {
        Loc l = Location::getLoc(cx, cy, board.x_size);
        if(board.colors[l] != C_EMPTY)
          return false; 
        cx += stepx;
        cy += stepy;
      }
      return true;
    }
  }
  return false;
}

bool GameLogic::isSquareAttacked(const Board& board, Loc sq, Player byPla) {
  int sx = Location::getX(sq, board.x_size);
  int sy = Location::getY(sq, board.x_size);
  for(int y = 0; y < board.y_size; y++)
    for(int x = 0; x < board.x_size; x++) {
      Loc from = Location::getLoc(x, y, board.x_size);
      Color c = board.colors[from];
      if(c == C_EMPTY || getPiecePla(c) != byPla)
        continue;
      if(pieceAttacksSquare(board, x, y, getPieceType(c), byPla, sx, sy))
        return true;
    }
  return false;
}

Loc GameLogic::findKing(const Board& board, Player pla) {
  Color target = getPiece(pla, C_KING);
  for(int y = 0; y < board.y_size; y++)
    for(int x = 0; x < board.x_size; x++) {
      Loc loc = Location::getLoc(x, y, board.x_size);
      if(board.colors[loc] == target)
        return loc;
    }
  return Board::NULL_LOC;
}

bool GameLogic::isInCheck(const Board& board, Player pla) {
  Loc k = findKing(board, pla);
  if(k == Board::NULL_LOC)
    return false;
  return isSquareAttacked(board, k, getOpp(pla));
}

void GameLogic::getPseudoLegalDests(const Board& board, Player pla, Loc from, std::vector<Loc>& out) {
  Color c = board.colors[from];
  Color pt = getPieceType(c);
  int xs = board.x_size;
  int ys = board.y_size;
  int fx = Location::getX(from, xs);
  int fy = Location::getY(from, xs);
  int f = forwardDY(pla);

  auto probe = [&](int x, int y) -> int {
    if(x < 0 || x >= xs || y < 0 || y >= ys)
      return -1;
    Color dc = board.colors[Location::getLoc(x, y, xs)];
    if(dc == C_EMPTY)
      return 0;
    if(getPiecePla(dc) == pla)
      return -1;
    return 1;
  };
  auto add = [&](int x, int y) { out.push_back(Location::getLoc(x, y, xs)); };

  switch(pt) {
    case C_KING:
      for(int ddx = -1; ddx <= 1; ddx++)
        for(int ddy = -1; ddy <= 1; ddy++) {
          if(ddx == 0 && ddy == 0)
            continue;
          if(probe(fx + ddx, fy + ddy) >= 0)
            add(fx + ddx, fy + ddy);
        }
      break;
    case C_MET:
    case C_BIAGAE: {
      static const int dd[4][2] = {{1, 1}, {1, -1}, {-1, 1}, {-1, -1}};
      for(auto& d : dd)
        if(probe(fx + d[0], fy + d[1]) >= 0)
          add(fx + d[0], fy + d[1]);
      break;
    }
    case C_KHON: {
      static const int dd[4][2] = {{1, 1}, {1, -1}, {-1, 1}, {-1, -1}};
      for(auto& d : dd)
        if(probe(fx + d[0], fy + d[1]) >= 0)
          add(fx + d[0], fy + d[1]);
      if(probe(fx, fy + f) >= 0) 
        add(fx, fy + f);
      break;
    }
    case C_KNIGHT: {
      static const int dd[8][2] = {
        {1, 2}, {2, 1}, {-1, 2}, {-2, 1}, {1, -2}, {2, -1}, {-1, -2}, {-2, -1}};
      for(auto& d : dd)
        if(probe(fx + d[0], fy + d[1]) >= 0)
          add(fx + d[0], fy + d[1]);
      break;
    }
    case C_ROOK: {
      static const int dd[4][2] = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
      for(auto& d : dd) {
        int cx = fx + d[0];
        int cy = fy + d[1];
        while(true) {
          int r = probe(cx, cy);
          if(r < 0)
            break;
          add(cx, cy);
          if(r == 1)
            break;  
          cx += d[0];
          cy += d[1];
        }
      }
      break;
    }
    case C_BIA:
      if(probe(fx, fy + f) == 0) 
        add(fx, fy + f);
      if(probe(fx - 1, fy + f) == 1)  
        add(fx - 1, fy + f);
      if(probe(fx + 1, fy + f) == 1)
        add(fx + 1, fy + f);
      break;
  }
  (void)ys;
}

bool GameLogic::moveIsKingSafe(const Board& board, Player pla, Loc from, Loc to) {
  Board copy(board);
  copy.colors[to] = copy.colors[from];
  copy.colors[from] = C_EMPTY;
  return !isInCheck(copy, pla);
}

bool GameLogic::pieceHasLegalMove(const Board& board, Player pla, Loc from) {
  std::vector<Loc> dests;
  getPseudoLegalDests(board, pla, from, dests);
  for(Loc to : dests)
    if(moveIsKingSafe(board, pla, from, to))
      return true;
  return false;
}

bool GameLogic::hasAnyLegalMove(const Board& board, Player pla) {
  for(int y = 0; y < board.y_size; y++)
    for(int x = 0; x < board.x_size; x++) {
      Loc from = Location::getLoc(x, y, board.x_size);
      Color c = board.colors[from];
      if(c == C_EMPTY || getPiecePla(c) != pla)
        continue;
      if(pieceHasLegalMove(board, pla, from))
        return true;
    }
  return false;
}

bool GameLogic::isLegal(const Board& board, const Rules& rules, Player pla, Loc loc) {
  (void)rules;
  if(pla != board.nextPla)
    return false;
  if(loc == Board::PASS_LOC)
    return false;
  if(!board.isOnBoard(loc))
    return false;

  if(board.stage == 0) {
    Color c = board.colors[loc];
    if(getPiecePla(c) != pla)
      return false;
    return pieceHasLegalMove(board, pla, loc);
  } else {
    Loc from = board.midLocs[0];
    Color cdest = board.colors[loc];
    if(cdest != C_EMPTY && getPiecePla(cdest) == pla)
      return false; 
    std::vector<Loc> dests;
    getPseudoLegalDests(board, pla, from, dests);
    bool found = false;
    for(Loc d : dests)
      if(d == loc) {
        found = true;
        break;
      }
    if(!found)
      return false;
    return moveIsKingSafe(board, pla, from, loc);
  }
}

GameLogic::MovePriority GameLogic::getMovePriorityAssumeLegal(
  const Board&, const BoardHistory&, Player, Loc) {
  return MP_NORMAL;
}

GameLogic::MovePriority GameLogic::getMovePriority(
  const Board& board, const BoardHistory& hist, Player pla, Loc loc) {
  if(!board.isLegal(loc, pla, hist.rules))
    return MP_ILLEGAL;
  return getMovePriorityAssumeLegal(board, hist, pla, loc);
}


static int makrukCountingLimitMoves(const Board& board, Player attacker) {
  int rooks = 0, khons = 0, knights = 0;
  for(int y = 0; y < board.y_size; y++)
    for(int x = 0; x < board.x_size; x++) {
      Color c = board.colors[Location::getLoc(x, y, board.x_size)];
      if(c == C_EMPTY || c == C_WALL || getPiecePla(c) != attacker)
        continue;
      switch(getPieceType(c)) {
        case C_ROOK: rooks++; break;
        case C_KHON: khons++; break;
        case C_KNIGHT: knights++; break;
        default: break;
      }
    }
  if(rooks >= 2) return 8;
  if(rooks >= 1) return 16;
  if(khons >= 2) return 22;
  if(knights >= 2) return 32;
  if(khons >= 1) return 44;
  if(knights >= 1) return 64;
  return 0;
}

GameLogic::MakrukCountState GameLogic::getMakrukCountState(const Board& board) {
  MakrukCountState state;
  state.usedPlies = board.movenumslc;

  if(board.numStonesOnBoard() == 2) {
    state.active = true;
    state.loneKingCount = true;
    return state;
  }

  Player loneSide = C_WALL;
  if(board.numPlaStonesOnBoard(P_BLACK) == 1)
    loneSide = P_BLACK;
  else if(board.numPlaStonesOnBoard(P_WHITE) == 1)
    loneSide = P_WHITE;

  if(loneSide != C_WALL) {
    state.active = true;
    state.loneKingCount = true;
    state.countedSide = loneSide;
    int limitMoves = makrukCountingLimitMoves(board, getOpp(loneSide));
    state.countClass = limitMoves;
    if(limitMoves == 0)
      return state;
    int limitPlies = 2 * (limitMoves - board.numStonesOnBoard());
    if(limitPlies <= 0)
      return state;
    state.limitPlies = limitPlies;
    state.remainingPlies = std::max(0, limitPlies - state.usedPlies);
    return state;
  }

  bool anyBia = false;
  for(int y = 0; y < board.y_size && !anyBia; y++)
    for(int x = 0; x < board.x_size; x++) {
      Color c = board.colors[Location::getLoc(x, y, board.x_size)];
      if(c != C_EMPTY && c != C_WALL && getPieceType(c) == C_BIA) { anyBia = true; break; }
    }
  if(!anyBia) {
    state.active = true;
    state.loneKingCount = false;
    state.countClass = 128;
    state.limitPlies = 128;
    state.remainingPlies = std::max(0, 128 - state.usedPlies);
  }
  return state;
}

Color GameLogic::checkWinnerAfterPlayed(
  const Board& board, const BoardHistory& hist, Player pla, Loc loc) {
  if(loc == Board::PASS_LOC)
    return getOpp(pla);  

  if(board.stage != 0)
    return C_WALL;

  Player sideToMove = board.nextPla;

  if(findKing(board, sideToMove) == Board::NULL_LOC)
    return getOpp(sideToMove);

  if(!hasAnyLegalMove(board, sideToMove)) {
    if(isInCheck(board, sideToMove))
      return getOpp(sideToMove); 
    return C_EMPTY;             
  }

  {
    Hash128 last = board.getSitHashNoStage(board.nextPla);
    int count = 0;
    for(size_t i = 0; i < hist.hashHistory.size(); i++)
      if(hist.hashHistory[i] == last)
        count++;
    if(count >= 3)
      return C_EMPTY;
  }

  if(hist.rules.maxmoves != 0 && hist.rules.maxmoves <= board.movenum)
    return C_EMPTY;
  if(hist.rules.maxmovesNoCapture != 0 && hist.rules.maxmovesNoCapture <= board.movenumslc)
    return C_EMPTY;

  {
    MakrukCountState count = getMakrukCountState(board);
    if(count.active && count.remainingPlies <= 0)
      return C_EMPTY;
  }

  return C_WALL;
}

GameLogic::ResultsBeforeNN::ResultsBeforeNN() {
  inited = false;
  winner = C_WALL;
  myOnlyLoc = Board::NULL_LOC;
}

void GameLogic::ResultsBeforeNN::init(const Board&, const BoardHistory&, Color) {
  if(inited)
    return;
  inited = true;
}
