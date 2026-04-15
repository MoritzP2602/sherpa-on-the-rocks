//Header file for process V2_2__d__d__d__d__O2_0__E2

#ifndef V2_2__d__d__d__d__O2_0__E2_on
#define V2_2__d__d__d__d__O2_0__E2_on
#include "AMEGIC++/String/Values.H"

extern "C" AMEGIC::Values* Getter_V2_2__d__d__d__d__O2_0__E2(AMEGIC::Basic_Sfuncs* bs);

namespace AMEGIC {

class V2_2__d__d__d__d__O2_0__E2 : public Values,
  public Basic_Zfunc,
  public Basic_Pfunc {
  Complex*  Z;
  int*      f;
  Complex*  c;
  Complex** M;
  int*      cl;
public:
  V2_2__d__d__d__d__O2_0__E2(Basic_Sfuncs* _BS);
  ~V2_2__d__d__d__d__O2_0__E2();
  void SetCouplFlav(std::vector<Complex>&);
  int NumberOfCouplings() { return 1; }
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
};
}

#endif
