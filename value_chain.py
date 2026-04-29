import pandas as pd

# Define the data for the robot value chain
value_chain_data = [
    {
        "Segment": "Upstream (핵심 부품/인프라)",
        "Category": "감속기 (Reducer)",
        "Function": "로봇 관절의 힘을 조절하고 정밀 제어",
        "Key Companies (Domestic/Global)": "에스피지(SPG), SBB테크, 하모닉드라이브(일), 나브테스코(일)"
    },
    {
        "Segment": "Upstream (핵심 부품/인프라)",
        "Category": "센서 (Sensors)",
        "Function": "시각(Vision), 촉각(Force/Torque) 인지",
        "Key Companies (Domestic/Global)": "에이딘로보틱스, 산일센서, 드림텍, 인텔(RealSense), 벨로다인(라이다)"
    },
    {
        "Segment": "Upstream (핵심 부품/인프라)",
        "Category": "제어기 및 구동부",
        "Function": "로봇의 움직임을 연산하고 명령 수행",
        "Key Companies (Domestic/Global)": "알에스오토메이션, 파스텍, 웰콘시스템즈, 보쉬렉스로스, 지멘스"
    },
    {
        "Segment": "Upstream (핵심 부품/인프라)",
        "Category": "반도체/AI 칩",
        "Function": "로봇용 AI 연산 및 두뇌 역할",
        "Key Companies (Domestic/Global)": "NVIDIA (Jetson), 퀄컴, 삼성전자, SK하이닉스"
    },
    {
        "Segment": "Midstream (로봇 제조/본체)",
        "Category": "산업용/협동 로봇",
        "Function": "공장 자동화 및 인간과의 협업 수행",
        "Key Companies (Domestic/Global)": "두산로보틱스, 레인보우로보틱스, 현대로보틱스, 로보스타, FANUC(일), ABB(스위스), 쿠카(독/중), 테라다인(덴)"
    },
    {
        "Segment": "Midstream (로봇 제조/본체)",
        "Category": "서비스 로봇",
        "Function": "배송, 순찰, 의료, 가정용 서비스 제공",
        "Key Companies (Domestic/Global)": "LG전자(CLOi), 로보티즈, 고영(의료), 베어로보틱스, 소프트뱅크 로보틱스, 스타쉽 테크놀로지스"
    },
    {
        "Segment": "Midstream (로봇 제조/본체)",
        "Category": "휴머노이드 (Physical AI)",
        "Function": "인간의 형태를 띈 범용 로봇",
        "Key Companies (Domestic/Global)": "테슬라(Optimus), 보스턴 다이내믹스(현대차), 피규어 AI, 노블 머신즈"
    },
    {
        "Segment": "Downstream (SW 및 서비스)",
        "Category": "시스템 통합 (SI)",
        "Function": "산업 현장에 로봇 설치 및 최적화",
        "Key Companies (Domestic/Global)": "현대오토에버, 포스코DX, 비포락스, 빅웨이브로보틱스"
    },
    {
        "Segment": "Downstream (SW 및 서비스)",
        "Category": "로봇 SW/플랫폼",
        "Function": "로봇 운영체제(ROS) 및 AI 모델",
        "Key Companies (Domestic/Global)": "마이크로소프트, 구글(DeepMind), 마로솔"
    },
    {
        "Segment": "Downstream (SW 및 서비스)",
        "Category": "RaaS (구독 서비스)",
        "Function": "로봇 대여 및 물류 자동화 솔루션",
        "Key Companies (Domestic/Global)": "아마존(RIVR), 배달의민족(우아한형제들)"
    }
]

# Define the trends data
trends_data = [
    {"Topic": "피지컬 AI (Physical AI) 결합", "Description": "NVIDIA 시뮬레이션 기술 등을 통해 로봇이 스스로 학습하고 복잡한 환경에 대응"},
    {"Topic": "휴머노이드 상용화", "Description": "테슬라 옵티머스, 현대차 아틀라스 등 인간형 로봇의 실제 공장 배치 및 상용화 가속"},
    {"Topic": "M&A 및 생태계 확장", "Description": "빅테크 기업(아마존 등)의 로보틱스 기업 인수를 통한 하드웨어 역량 내재화"}
]

df_value_chain = pd.DataFrame(value_chain_data)
df_trends = pd.DataFrame(trends_data)

file_path = 'Robot_Value_Chain_Analysis_2026.xlsx'

with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
    # 1. Write Value Chain Sheet
    df_value_chain.to_excel(writer, sheet_name='로봇 밸류체인', index=False)
    workbook = writer.book
    worksheet = writer.sheets['로봇 밸류체인']
    
    # Add formats
    header_format = workbook.add_format({
        'bold': True,
        'text_wrap': True,
        'valign': 'vcenter',
        'align': 'center',
        'fg_color': '#D7E4BC',
        'border': 1
    })
    
    cell_format = workbook.add_format({
        'valign': 'vcenter',
        'border': 1,
        'text_wrap': True
    })

    # Set column widths and format
    worksheet.set_column('A:A', 25, cell_format)
    worksheet.set_column('B:B', 20, cell_format)
    worksheet.set_column('C:C', 35, cell_format)
    worksheet.set_column('D:D', 60, cell_format)
    
    for col_num, value in enumerate(df_value_chain.columns.values):
        worksheet.write(0, col_num, value, header_format)

    # 2. Write Trends Sheet
    df_trends.to_excel(writer, sheet_name='2026 시장 트렌드', index=False)
    worksheet_trends = writer.sheets['2026 시장 트렌드']
    
    worksheet_trends.set_column('A:A', 30, cell_format)
    worksheet_trends.set_column('B:B', 70, cell_format)
    
    for col_num, value in enumerate(df_trends.columns.values):
        worksheet_trends.write(0, col_num, value, header_format)

print(f"File saved as {file_path}")
