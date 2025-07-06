 #include "interaction_lib.h"

#include <google/protobuf/stubs/port.h>
#include <nlohmann/json.hpp>
#include <nlohmann/json_fwd.hpp>
#include <set>

#include "ou_names.h"

namespace ou_modules_bot_interaction {

constexpr int EPHEMERAL = 1 << 6;
constexpr int INTERACTION_COMMAND = 2;
constexpr int INTERACTION_MESSAGE = 3;

class Handler::Impl {
public:
  Impl(nlohmann::json::const_reference request_json) {
    nlohmann::json::const_reference data = request_json["data"];
    if (request_json["type"] == INTERACTION_MESSAGE) {
        target_id_ = data["target_id"];
        message_ = data["/resolved/messages"_json_pointer][target_id_];
    } else {
      for (const auto& option : data["options"]) {
        if (option["name"] == "modules") {
          message_["content"] = option["value"];
          message_["channel_id"] = request_json["channel_id"];
          break;
        }
      }
    }
    guild_id_ = request_json.value("guild_id", "@me");
    token_ = request_json["token"];
    interaction_id_ = request_json["id"];
    should_pubsub_ = false;
  }
  std::string Handle() {
    ou_modules_bot::OUNames names(message_.value("content", ""));
    nlohmann::json item;
    std::set<std::string> seen;
    ou_modules_bot::OUNames::Iterator it = names.GetIterator();
    while (it.NextItem(item)) {
      if (item.is_null()) {
        should_pubsub_ = true;
        return MakePubSubResult();
      }
      if (seen.find(item["code"]) == seen.end()) {
        seen.insert(item["code"]);
        fields_.push_back(CreateEmbedField(item));
      }
    }

    return MakeResult(item);
  }
  nlohmann::json PubSubJson() {
    nlohmann::json pubsub_json;
    pubsub_json["guild_id"] = guild_id_;
    pubsub_json["target_id"] = target_id_;
    pubsub_json["message"] = message_;
    pubsub_json["token"] = token_;
    pubsub_json["interaction_id"] = interaction_id_;
    return pubsub_json;
  }
  bool ShouldForwardToSlowBot() { return should_pubsub_; }

private:
  std::string MakeResult(nlohmann::json::const_reference last_item) {
    nlohmann::json data;
    if (fields_.size() > 1) {
      embeds_[0]["fields"] = fields_;
      data["embeds"] = std::move(embeds_);
    } else if (fields_.size() == 1) {
      // Embeds not needed - only one result, can be passed as content.
      data["content"] = MakePlainTextContent(last_item);
    } else {
      data["content"] = "No modules found.";
      data["flags"] = EPHEMERAL;
    }
    std::string channel_id = message_["channel_id"];
    nlohmann::json button = {
        {{"type", 2},  // Button
         {"style", 5}, // Link
         {"label", "Jump to referenced message"},
         {"url", "https://discord.com/channels/" + std::string(guild_id_) +
                     "/" + std::string(channel_id) + "/" +
                     std::string(target_id_)}}};

    data["components"] = {{{"type", 1}, // Action Row
                           {"components", button}}};

    nlohmann::json result_json = {
        {"type", 4}, // CHANNEL_MESSAGE_WITH_SOURCE
        {"data", data},
    };
    return result_json.dump();
  }

  static nlohmann::json CreateEmbedField(nlohmann::json::const_reference item) {
    nlohmann::json field;
    field["name"] = item["code"];
    std::string full_name = item["full_name"];
    if (!item["url"].is_null()) {
      field["value"] =
          " * [" + full_name + "](<" + std::string(item["url"]) + ">)";
    } else {
      field["value"] = " * " + full_name;
    }
    return field;
  }

  static std::string
  MakePlainTextContent(nlohmann::json::const_reference item) {
    std::string code = item["code"];
    std::string full_name = item["full_name"];
    if (!item["url"].is_null()) {
      return code + ": [" + full_name + "](<" + std::string(item["url"]) + ">)";
    } else {
      return code + ": " + full_name;
    }
  }

  std::string MakePubSubResult() {
    return "{\"type\": 5}";
  }

  std::string guild_id_;
  std::string target_id_;
  std::string token_;
  std::string interaction_id_;
  nlohmann::json message_;
  std::vector<nlohmann::json> fields_;
  std::array<nlohmann::json, 1> embeds_ = {nlohmann::json()};
  bool should_pubsub_;
};

Handler::Handler(nlohmann::json::const_reference request_json) {
  impl_ = std::make_unique<Impl>(request_json);
}
Handler::~Handler() = default;

std::string Handler::Handle() { return impl_->Handle(); }

bool Handler::ShouldForwardToSlowBot() { return impl_->ShouldForwardToSlowBot(); }

std::string Handler::PubSubJsonDump() { return impl_->PubSubJson().dump(); }

} // namespace ou_modules_bot_interaction
