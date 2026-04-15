//Header file for process V2_3__d__d__G__d__d__O3_0

#ifndef V2_3__d__d__G__d__d__O3_0_on
#define V2_3__d__d__G__d__d__O3_0_on
#include "AMEGIC++/String/Values.H"

extern "C" AMEGIC::Values* Getter_V2_3__d__d__G__d__d__O3_0(AMEGIC::Basic_Sfuncs* bs);

namespace AMEGIC {

class V2_3__d__d__G__d__d__O3_0 : public Values,
  public Basic_Zfunc,
  public Basic_Xfunc,
  public Basic_Vfunc,
  public Basic_Pfunc {
  Complex*  Z;
  int*      f;
  Complex*  c;
  Complex** M;
  int*      cl;
public:
  V2_3__d__d__G__d__d__O3_0(Basic_Sfuncs* _BS);
  ~V2_3__d__d__G__d__d__O3_0();
  void SetCouplFlav(std::vector<Complex>&);
  int NumberOfCouplings() { return 4; }
  Complex Evaluate(int,int);
  void    Calculate();
  void Calculate_M0();
  void Calculate_M1();
  void Calculate_M2();
  void Calculate_M3();
  void Calculate_M4();
  void Calculate_M5();
  void Calculate_M6();
  void Calculate_M7();
  void Calculate_M8();
  void Calculate_M9();
  void Calculate_M10();
  void Calculate_M11();
  void Calculate_M12();
  void Calculate_M13();
  void Calculate_M14();
  void Calculate_M15();
  void Calculate_M16();
  void Calculate_M17();
  void Calculate_M18();
  void Calculate_M19();
  void Calculate_M20();
  void Calculate_M21();
  void Calculate_M22();
  void Calculate_M23();
  void Calculate_M24();
  void Calculate_M25();
  void Calculate_M26();
  void Calculate_M27();
  void Calculate_M28();
  void Calculate_M29();
  void Calculate_M30();
  void Calculate_M31();
};
}

#endif
