import json
import logging
from borneo import (
    NoSQLHandle,
    NoSQLHandleConfig,
    Regions,
    PutRequest,
    QueryRequest,
    PrepareRequest
)
from borneo.iam import SignatureProvider
from config.setting import Setting
import traceback

class NoSQLRepository:
    def __init__(self, logger):
        self.compartment_id = Setting.COMPARTMENT_OCID
        self.region = Regions.AP_CHUNCHEON_1
        self.table_name = Setting.NOSQL_TABLE_NAME
        self.logger = logger.getChild("NoSQL")

        self.handle = self.create_handle()
        self.check_stmt = None
        if self.handle:
            self.prepare_check_query()

    def create_handle(self):
        try:
            provider = SignatureProvider()
            config = NoSQLHandleConfig(self.region, provider).set_default_compartment(self.compartment_id)
            
            handle = NoSQLHandle(config)
            self.logger.debug("✅  핸들 생성 성공")
            return handle
        except Exception as e:
            self.logger.error(f"❌  핸들 생성 실패: {e}")
            traceback.print_exc()
            return None

    def prepare_check_query(self):
        try:
            sql_text = f"DECLARE $url STRING; SELECT 1 FROM {self.table_name} WHERE source_url = $url LIMIT 1"
            
            prep_req = PrepareRequest().set_statement(sql_text)
            prep_res = self.handle.prepare(prep_req)
            
            self.check_stmt = prep_res.get_prepared_statement()
            self.logger.debug("⚡  중복 확인 쿼리 Prepare 완료")
            
        except Exception as e:
            self.logger.warning(f"⚠️  쿼리 Prepare 실패 (일반 쿼리로 대체됨): {e}")
            self.check_stmt = None

    def exists_by_url(self, url):
        if not self.handle:
            return False

        try:
            query_req = QueryRequest()

            if self.check_stmt:
                self.check_stmt.set_variable("$url", url)
                query_req.set_prepared_statement(self.check_stmt)
            else:
                sql = f"DECLARE $url STRING; SELECT 1 FROM {self.table_name} WHERE source_url = $url LIMIT 1"
                query_req.set_statement(sql)
                query_req.set_prepared_statement_variables({"$url": url})

            result = self.handle.query(query_req)
            results = result.get_results()
            
            return len(results) > 0

        except Exception as e:
            self.logger.error(f"⚠️  중복 조회 오류: {e}")
            return False

    def save_raw_job(self, platform, job_data):
        if not self.handle:
            self.logger.warning("⚠️  NoSQL 핸들이 초기화되지 않아 저장을 건너뜁니다.")
            return False

        try:
            unique_url = job_data.get('job_url')

            if not unique_url:
                self.logger.warning(f"[{platform}] ⚠️  URL이 없어 저장을 건너뜁니다.")
                return False

            if self.exists_by_url(unique_url):
                self.logger.debug(f"⏭️ 이미 존재하는 공고 (Skip): {unique_url}")
                return False
            
            row_to_put = {
                'source_url': unique_url,
                'platform': platform,
                'raw_json_content': json.dumps(job_data, ensure_ascii=False)
            }

            req = PutRequest().set_table_name(self.table_name).set_value(row_to_put)
            self.handle.put(req)
            self.logger.debug(f"💾 저장 성공: {unique_url}")
            return True

        except Exception as e:
            self.logger.error(f"❌ 저장 실패 (ID: {job_data.get('id')}): {e}", exc_info=True)
            traceback.print_exc()
            return False

    def close(self):
        if self.handle:
            self.handle.close()
            self.logger.info("🔒  핸들 종료")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()