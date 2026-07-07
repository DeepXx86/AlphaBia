/*
 * gamelogic.h
 * Logics of game rules
 * Some other game logics are in board.h/cpp
 *
 * Makruk
 */

#ifndef GAME_GAMELOGIC_H_
#define GAME_GAMELOGIC_H_

#include <vector>

#include "../game/boardhistory.h"

/*
* Other game logics:
* Board::
*/

namespace GameLogic {

  typedef char MovePriority;
  static const MovePriority MP_NORMAL = 126;
  static const MovePriority MP_SUDDEN_WIN = 1;//win after this move
  static const MovePriority MP_ONLY_NONLOSE_MOVES = 2;//the only non-lose moves
  static const MovePriority MP_WINNING = 3;//sure win, but not this move
  static const MovePriority MP_ILLEGAL = -1;//illegal moves

  int forwardDY(Player pla);
  int promotionRankY(Player pla, int ySize);

  bool isInTrap(Loc loc, Player pla);
  bool isInRiver(Loc loc);
  Loc getHomeLoc(Player pla);

  bool isSquareAttacked(const Board& board, Loc sq, Player byPla);
  Loc findKing(const Board& board, Player pla);
  bool isInCheck(const Board& board, Player pla);
  void getPseudoLegalDests(const Board& board, Player pla, Loc from, std::vector<Loc>& out);
  bool moveIsKingSafe(const Board& board, Player pla, Loc from, Loc to);
  bool pieceHasLegalMove(const Board& board, Player pla, Loc from);
  bool hasAnyLegalMove(const Board& board, Player pla);

  bool isLegal(const Board& board, const Rules& rules, Player pla, Loc loc);

  MovePriority getMovePriorityAssumeLegal(const Board& board, const BoardHistory& hist, Player pla, Loc loc);
  MovePriority getMovePriority(const Board& board, const BoardHistory& hist, Player pla, Loc loc);

  //C_EMPTY = draw, C_WALL = not finished 
  Color checkWinnerAfterPlayed(const Board& board, const BoardHistory& hist, Player pla, Loc loc);


  //some results calculated before calculating NN
  //part of NN input, and then change policy/value according to this
  struct ResultsBeforeNN {
    bool inited;
    Color winner;
    Loc myOnlyLoc;
    ResultsBeforeNN();
    void init(const Board& board, const BoardHistory& hist, Color nextPlayer);
  };
}




#endif // GAME_RULELOGIC_H_
