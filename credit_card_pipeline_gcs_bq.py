from airflow.models import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.providers.mysql.hooks.mysql import MySqlHook
from airflow.utils.dates import days_ago
import pandas as pd


MYSQL_CONNECTION = "mysql_default"   # ชื่อของ connection ใน Airflow ที่เซ็ตเอาไว้

# path ที่จะใช้
application_output_path = "/home/airflow/gcs/data/application_data.csv"
credits_output_path = "/home/airflow/gcs/data/credits_record_data.csv"
final_output_path = "/home/airflow/gcs/data/output_data.csv"


def get_application_data(application_path):
    
    # เรียกใช้ MySqlHook เพื่อต่อไปยัง MySQL
    mysqlserver = MySqlHook(MYSQL_CONNECTION)
    
    # Query จาก database โดยใช้ Hook ที่สร้าง ผลลัพธ์ได้ pandas DataFrame
    application_data = mysqlserver.get_pandas_df(sql="SELECT * FROM application_record")

    # Save ไฟล์ CSV ไปที่ application_path ("/home/airflow/gcs/data/application_data.csv")
    # จะไปอยู่ที่ GCS โดยอัตโนมัติ
    application_data.to_csv(application_path, index=False)
    print(f"Output to {application_path}")


def get_credits_record_data(credits_path):
    # เรียกใช้ MySqlHook เพื่อต่อไปยัง MySQL
    mysqlserver2 = MySqlHook(MYSQL_CONNECTION)

    # Query จาก database และให้ได้ผลลัพธ์  pandas DataFrame
    credits_data = mysqlserver2.get_pandas_df(sql = "SELECT * FROM credit_record")

    # Save ไฟล์ CSV ไปที่ credits_path ("/home/airflow/gcs/data/credits_record_data.csv")
    # จะไปอยู่ที่ GCS โดยอัตโนมัติ
    credits_data.to_csv(credits_path, index=False)
    print(f"Output to {credits_path}")


def merge_data(application_path, credits_path, output_path):
    # Read CSV
    application = pd.read_csv(application_path)
    credits = pd.read_csv(credits_path)
    
    # Merge data
    final_df = application.merge(credits, how="left", left_on="ID", right_on="ID")
    
    # rename columns 

    final_df.rename(columns={
        'CODE_GENDER': 'gender',
        'FLAG_OWN_CAR': 'own_car',
        'FLAG_OWN_REALTY': 'own_property',
        'CNT_CHILDREN': 'children',
        'AMT_INCOME_TOTAL': 'income',
        'NAME_INCOME_TYPE': 'income_type',
        'NAME_EDUCATION_TYPE': 'education',
        'NAME_FAMILY_STATUS': 'famoily_status',
        'NAME_HOUSING_TYPE': 'housing_type',
        'FLAG_MOBIL': 'mobile',
        'FLAG_WORK_PHONE': 'work_phone',
        'FLAG_PHONE': 'phone',
        'FLAG_EMAIL': 'email',
        'CNT_FAM_MEMBERS': 'family_members',
        'MONTHS_BALANCE': 'months_balance',
        'STATUS': 'status',
        'DAYS_BIRTH': 'age_in_days',
        'DAYS_EMPLOYED': 'employment_in_day',
        'OCCUPATION_TYPE': 'Occupation'

    }, inplace=True)

    # save ไฟล์ CSV
    final_df.to_csv(output_path, index=False)
    print(f"Output to {output_path}")
    print("== End ==")


with DAG(
    "demo_credit_approval",
    start_date=days_ago(1),
    schedule_interval="@once",
    tags=["dataen"]
) as dag:

   
    t1 = PythonOperator(
        task_id="get_application_data",
        python_callable=get_application_data,
        op_kwargs={"application_path": application_output_path},
    )

    t2 = PythonOperator(
        task_id="get_credit_record_data",
        python_callable=get_credits_record_data,
        op_kwargs={"credits_path": credits_output_path},
    )

    t3 = PythonOperator(
        task_id="merge_data_and_rename_columns",
        python_callable=merge_data,
        op_kwargs={
            "application_path": application_output_path,
            "credits_path": credits_output_path, 
            "output_path": final_output_path
        },
    )

    t4 = BashOperator(
        task_id="load_to_bq",
        bash_command="bq load --source_format=csv --autodetect [DATASET].[TABLE_NAME]  gs:// [GCS_BUCKET]/data/output_data.csv"
    )

    # task dependencies
    [t1, t2] >> t3 >> t4
