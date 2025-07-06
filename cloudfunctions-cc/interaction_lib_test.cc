#include "interaction_lib.h"
#include <gtest/gtest.h>
#include <nlohmann/json.hpp>
#include <nlohmann/json_fwd.hpp>
#include <string>

nlohmann::json MakeRequest(std::string content) {
  nlohmann::json request = R"({
        "type": 2,
        "data": {
            "target_id": "foo",
            "resolved": {
                "messages": {
                    "foo": {
                        "channel_id": "fake_channel_id"
                    }
                }
            }
        },
        "guild_id": "fake_guild_id",
        "token": "fake_token",
        "id": "fake_request_id"
    })"_json;
  request["data"]["resolved"]["messages"]["foo"]["content"] = content;
  return request;
}

nlohmann::json GetResponseTemplate() {
  return R"({
        "type": 4,
        "data": {
            "components": [{
                "type": 1,
                "components": [{
                    "type": 2,
                    "style": 5,
                    "label": "Jump to referenced message",
                    "url": "https://discord.com/channels/fake_guild_id/fake_channel_id/foo"
                }]
            }]
        }
    })"_json;
}

nlohmann::json MakeResponseWithOneModule(std::string code,
                                         std::string full_name,
                                         std::string url) {
  auto response = GetResponseTemplate();
  response["data"]["content"] = code + ": [" + full_name + "](<" + url + ">)";
  return response;
}

nlohmann::json MakeResponseWithTwoModules(std::string code1,
                                          std::string full_name1,
                                          std::string url1, std::string code2,
                                          std::string full_name2,
                                          std::string url2) {
  auto response = GetResponseTemplate();
  response["data"]["embeds"] = R"([{
    "fields": [{}, {}]
  }])"_json;
  response["data"]["embeds"][0]["fields"][0]["name"] = code1;
  response["data"]["embeds"][0]["fields"][0]["value"] =
      " * [" + full_name1 + "](<" + url1 + ">)";
  response["data"]["embeds"][0]["fields"][1]["name"] = code2;
  response["data"]["embeds"][0]["fields"][1]["value"] =
      " * [" + full_name2 + "](<" + url2 + ">)";

  return response;
}

TEST(InteractionLibTest, Handler_Handle_SingleKnownModule) {
  nlohmann::json request = MakeRequest("M208");

  ou_modules_bot_interaction::Handler handler(request);
  nlohmann::json result = nlohmann::json::parse(handler.Handle());

  EXPECT_EQ(result, MakeResponseWithOneModule(
                        "M208", "Pure mathematics",
                        "http://www.open.ac.uk/courses/modules/m208"));
}

TEST(InteractionLibTest, Handler_Handle_TwoKnownModules) {
  nlohmann::json request = MakeRequest("m208 mst125");

  ou_modules_bot_interaction::Handler handler(request);
  nlohmann::json result = nlohmann::json::parse(handler.Handle());

  EXPECT_EQ(result, MakeResponseWithTwoModules(
                        "M208", "Pure mathematics",
                        "http://www.open.ac.uk/courses/modules/m208", "MST125",
                        "Essential mathematics 2",
                        "http://www.open.ac.uk/courses/modules/mst125"));
}

TEST(InteractionLibTest, Handler_Handle_ForwardToSlowBot) {
  nlohmann::json request = MakeRequest("M999");
  ou_modules_bot_interaction::Handler handler(request);

  EXPECT_EQ(handler.Handle(), R"({"type": 5})");

  EXPECT_TRUE(handler.ShouldForwardToSlowBot());
  EXPECT_EQ(nlohmann::json::parse(handler.PubSubJsonDump()), R"({
    "interaction_id": "fake_request_id",
    "message": {"channel_id": "fake_channel_id", "content": "M999"},
    "target_id": "foo",
    "guild_id": "fake_guild_id",
    "token": "fake_token"})"_json);
}

TEST(InteractionLibTest, Handler_Handle_ForwardToSlowBot_3Modules) {
  nlohmann::json request = MakeRequest("T313 & T329 & M999");
  ou_modules_bot_interaction::Handler handler(request);

  EXPECT_EQ(handler.Handle(), R"({"type": 5})");

  EXPECT_TRUE(handler.ShouldForwardToSlowBot());
  EXPECT_EQ(nlohmann::json::parse(handler.PubSubJsonDump()), R"({
    "interaction_id": "fake_request_id",
    "message": {"channel_id": "fake_channel_id", "content": "T313 & T329 & M999"},
    "target_id": "foo",
    "guild_id": "fake_guild_id",
    "token": "fake_token"})"_json);
}

int main(int argc, char **argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
